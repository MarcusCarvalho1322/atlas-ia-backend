"""
atlas-geo — backend do ATLAS-IA (Sistema de Defesa Ambiental)

Resolve, em um único serviço, os dois problemas mais sérios encontrados na
avaliação do app hoje (100% front-end, sem servidor nenhum):

  1. Segurança: a chave da Anthropic deixa de ser pedida ao usuário e de
     trafegar pelo navegador — fica só aqui, em variável de ambiente.
  2. Continuidade: os casos deixam de viver só no localStorage de um
     navegador específico — passam a ficar num banco de dados de verdade.

E adiciona a funcionalidade que dá nome ao projeto:
  3. Geo: cruzamento automático das coordenadas do caso contra as bases
     públicas e oficiais de desmatamento do INPE (DETER + PRODES).

Nenhuma tese jurídica, dado de caso ou fonte foi inventada — ver
geo_service.py e ai_service.py para a proveniência de cada peça.
"""
import os
from datetime import date
from typing import Optional, Any

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import Base, engine, get_db
from models import Caso
import geo_service
import ai_service
import catalogo

Base.metadata.create_all(bind=engine)

APP_API_TOKEN = os.getenv("ATLAS_API_TOKEN", "")  # opcional, mas recomendado — mesmo padrão do browser-use-server
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

app = FastAPI(title="ATLAS-IA · atlas-geo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _checar_auth(authorization: Optional[str]):
    if not APP_API_TOKEN:
        return  # auth desligada — ok para teste, não recomendado em produção
    if not authorization or not authorization.startswith("Bearer ") or authorization[7:].strip() != APP_API_TOKEN:
        raise HTTPException(401, "Token inválido ou ausente")


# ───────────────────────── saúde / info ─────────────────────────
@app.get("/")
def root():
    return {
        "service": "ATLAS-IA · atlas-geo",
        "checks": {
            "anthropic_key_set": bool(ai_service.ANTHROPIC_API_KEY),
            "auth_required": bool(APP_API_TOKEN),
        },
    }


@app.get("/health")
def health():
    return {"ok": True}


# ───────────────────────── Catálogo de auditoria ─────────────────────────
# Fonte única de verdade: o front-end lê os itens daqui em vez de tê-los
# escritos no próprio código (que era onde a duplicação vivia).

@app.get("/api/catalogo")
def obter_catalogo(authorization: Optional[str] = Header(None)):
    _checar_auth(authorization)
    return catalogo.carregar()


class AuditoriaRequest(BaseModel):
    respostas: dict[str, str]          # {"1.1": "ok" | "fail" | "na", ...}
    casoId: Optional[str] = None       # se informado, o resultado é gravado no caso


@app.post("/api/auditoria")
def executar_auditoria(
    req: AuditoriaRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    _checar_auth(authorization)
    resultado = catalogo.executar_auditoria(req.respostas)
    if req.casoId:
        caso = db.query(Caso).filter(Caso.id == req.casoId).first()
        if caso:
            caso.audit_result = resultado
            db.commit()
    return resultado


# ───────────────────────── IA: diagnóstico + peças ─────────────────────────
class DiagnosticoRequest(BaseModel):
    formData: dict[str, Any]
    auditResult: Optional[dict[str, Any]] = None


class PecaRequest(BaseModel):
    pecaId: int
    formData: dict[str, Any]
    auditResult: Optional[dict[str, Any]] = None


@app.post("/api/diagnostico")
def diagnostico(req: DiagnosticoRequest, authorization: Optional[str] = Header(None)):
    _checar_auth(authorization)
    try:
        texto = ai_service.gerar_diagnostico(req.formData, req.auditResult)
        return {"ok": True, "output": texto}
    except Exception as e:
        raise HTTPException(502, f"Falha ao gerar diagnóstico: {e}")


@app.post("/api/peca")
def peca(req: PecaRequest, authorization: Optional[str] = Header(None)):
    _checar_auth(authorization)
    try:
        texto = ai_service.gerar_peca(req.pecaId, req.formData, req.auditResult)
        return {"ok": True, "output": texto}
    except Exception as e:
        raise HTTPException(502, f"Falha ao gerar peça: {e}")


# ───────────────────────── Casos (substitui o localStorage) ─────────────────────────
class CasoIn(BaseModel):
    formData: dict[str, Any]
    auditResult: Optional[dict[str, Any]] = None


@app.get("/api/casos")
def listar_casos(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    _checar_auth(authorization)
    casos = db.query(Caso).order_by(Caso.saved_at.desc()).all()
    return [c.to_dict() for c in casos]


@app.post("/api/casos")
def salvar_caso(req: CasoIn, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    _checar_auth(authorization)
    caso = Caso(form_data=req.formData, audit_result=req.auditResult)
    db.add(caso)
    db.commit()
    db.refresh(caso)
    return caso.to_dict()


@app.get("/api/casos/{caso_id}")
def obter_caso(caso_id: str, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    _checar_auth(authorization)
    caso = db.query(Caso).filter(Caso.id == caso_id).first()
    if not caso:
        raise HTTPException(404, "Caso não encontrado")
    return caso.to_dict()


@app.delete("/api/casos/{caso_id}")
def excluir_caso(caso_id: str, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    _checar_auth(authorization)
    caso = db.query(Caso).filter(Caso.id == caso_id).first()
    if not caso:
        raise HTTPException(404, "Caso não encontrado")
    db.delete(caso)
    db.commit()
    return {"ok": True}


# ───────────────────────── Geo: cruzamento com satélite (INPE) ─────────────────────────
class GeoVerificarRequest(BaseModel):
    lat: float
    lon: float
    bioma: str
    dataFato: Optional[date] = None
    raioGraus: Optional[float] = None
    casoId: Optional[str] = None  # se informado, o resultado é anexado ao histórico do caso


@app.post("/api/geo/verificar")
async def geo_verificar(
    req: GeoVerificarRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    _checar_auth(authorization)
    resultado = await geo_service.verificar_coordenada(
        lat=req.lat,
        lon=req.lon,
        bioma=req.bioma,
        data_fato=req.dataFato,
        raio_graus=req.raioGraus or geo_service.RAIO_GRAUS_PADRAO,
    )
    if not resultado.get("ok"):
        raise HTTPException(400, resultado.get("erro", "Falha na verificação geoespacial"))

    if req.casoId:
        caso = db.query(Caso).filter(Caso.id == req.casoId).first()
        if caso:
            historico = caso.geo_verificacoes or []
            historico.append(resultado)
            caso.geo_verificacoes = historico
            db.commit()

    return resultado
