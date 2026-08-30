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
from pathlib import Path
from typing import Optional, Any

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import Base, engine, get_db, SessionLocal
from models import Caso, Prospecto
import geo_service
import ai_service
import catalogo
import prospeccao
import rotina
import enriquecimento

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


@app.on_event("startup")
async def _iniciar_agendador():
    import asyncio
    asyncio.create_task(rotina.agendador(SessionLocal, BASE_IBAMA))


@app.get("/api/prospeccao/ultima-execucao")
def ultima_execucao(authorization: Optional[str] = Header(None)):
    """Quando a rotina rodou pela última vez e com que resultado."""
    _checar_auth(authorization)
    return {
        "agendada_para_hora_utc": os.getenv("ROTINA_DIARIA_HORA") or None,
        **rotina.ultima_execucao,
    }


# ───────────────────────── Prospecção ─────────────────────────
# Identificação, seleção e mineração de casos na base pública do IBAMA.
# Devolve apenas constatação aritmética; a leitura jurídica não passa por aqui.

BASE_IBAMA = os.getenv("BASE_IBAMA_DIR", "./dados_ibama")
_cache_casos: dict[int, list] = {}


def _casos(ano: int):
    if ano not in _cache_casos:
        arq = Path(BASE_IBAMA) / f"auto_infracao_{ano}.csv"
        if not arq.exists():
            raise HTTPException(404, f"Base de {ano} ainda não baixada. Chame POST /api/prospeccao/atualizar.")
        _cache_casos[ano] = prospeccao.ingerir(arq)
    return _cache_casos[ano]


@app.post("/api/prospeccao/atualizar")
def atualizar_base(ano: Optional[int] = None, authorization: Optional[str] = Header(None)):
    """Rebaixa o pacote do IBAMA (republicado diariamente) para o ano indicado."""
    _checar_auth(authorization)
    ano = ano or date.today().year
    try:
        arquivos = prospeccao.baixar_base(BASE_IBAMA, [ano])
    except Exception as e:
        raise HTTPException(502, f"Falha ao baixar a base do IBAMA: {e}")
    if not arquivos:
        raise HTTPException(404, f"O pacote do IBAMA não contém dados de {ano}.")
    _cache_casos.pop(ano, None)
    casos = _casos(ano)
    return {"ok": True, "ano": ano, "casos_vivos": len(casos), "fonte": prospeccao.FONTE}


@app.get("/api/prospeccao/resumo")
def prospeccao_resumo(ano: Optional[int] = None, authorization: Optional[str] = Header(None)):
    _checar_auth(authorization)
    return prospeccao.resumo(_casos(ano or date.today().year))


@app.get("/api/prospeccao/ranking")
def prospeccao_ranking(
    ano: Optional[int] = None, uf: Optional[str] = None,
    valor_minimo: Optional[float] = None, sinal: Optional[str] = None,
    topo: int = 50, revelar_documento: bool = False,
    authorization: Optional[str] = Header(None),
):
    """
    Ranking de casos por relevância. O nome do autuado só é devolvido com
    `revelar_documento=true` — use apenas onde houver base legal registrada
    para o tratamento com finalidade de prospecção comercial.
    """
    _checar_auth(authorization)
    sel = prospeccao.ranquear(_casos(ano or date.today().year), uf=uf,
                              valor_minimo=valor_minimo, sinal=sinal, topo=min(topo, 500))
    return {
        "total": len(sel),
        "fonte": prospeccao.FONTE, "fonte_url": prospeccao.FONTE_URL,
        "casos": [c.to_dict(revelar_documento=revelar_documento) for c in sel],
        "aviso": ("Sinais aritméticos apurados sobre o registro público. Não constituem "
                  "qualificação jurídica nem avaliação de mérito do auto de infração."),
    }


# ───────────────────────── Contato do caso ─────────────────────────

@app.get("/api/prospeccao/{num_auto}/contato")
def contato_do_caso(num_auto: str, authorization: Optional[str] = Header(None),
                    db: Session = Depends(get_db)):
    """
    Resolve o contato do autuado — quando existe fonte legítima para isso.

    Empresa: consulta o cadastro público da Receita Federal e devolve endereço,
    telefone e situação cadastral. Pessoa física: não há fonte pública de
    contato a partir de CPF, e o sistema não recorre a base de origem não
    verificável — devolve o caminho de aproximação por canal local.
    """
    _checar_auth(authorization)
    p = db.query(Prospecto).filter(Prospecto.num_auto == num_auto).first()
    if not p:
        raise HTTPException(404, "Auto não encontrado na carteira.")
    return {"num_auto": p.num_auto, "contato": enriquecimento.contato_do_caso(db, p)}


@app.get("/api/prospeccao/territorio")
def territorio(tipo_pessoa: str = "PF", topo: int = 50,
               authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """Onde os casos se concentram — a rota de aproximação para pessoa física."""
    _checar_auth(authorization)
    return enriquecimento.territorio(db, tipo_pessoa=tipo_pessoa, topo=min(topo, 200))


# ───────────────────────── Rotina diária de mineração ─────────────────────────

@app.post("/api/prospeccao/rotina-diaria")
def executar_rotina(
    ano: Optional[int] = None, baixar: bool = True,
    authorization: Optional[str] = Header(None), db: Session = Depends(get_db),
):
    """
    Baixa a base do dia, concilia com a carteira e devolve o boletim.
    Ponto único de entrada para o agendamento (cron do Railway ou tarefa externa).
    """
    _checar_auth(authorization)
    try:
        sinc = rotina.sincronizar(db, ano=ano, baixar=baixar, pasta=BASE_IBAMA)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(502, f"Falha na rotina de mineração: {e}")
    _cache_casos.clear()
    return {"sincronizacao": sinc, "boletim": rotina.boletim(db)}


@app.get("/api/prospeccao/boletim")
def obter_boletim(
    limiar_urgencia: int = 5, topo: int = 20, revelar_documento: bool = False,
    authorization: Optional[str] = Header(None), db: Session = Depends(get_db),
):
    """O boletim do dia, sem rebaixar a base."""
    _checar_auth(authorization)
    return rotina.boletim(db, limiar_urgencia=limiar_urgencia, topo=topo,
                          revelar_documento=revelar_documento)


class StatusProspecto(BaseModel):
    status: str          # novo|selecionado|contatado|descartado|cliente
    notas: Optional[str] = None


@app.patch("/api/prospeccao/{num_auto}")
def atualizar_prospecto(
    num_auto: str, req: StatusProspecto,
    authorization: Optional[str] = Header(None), db: Session = Depends(get_db),
):
    """Move o caso no funil. A rotina diária nunca sobrescreve esta decisão."""
    _checar_auth(authorization)
    validos = {"novo", "selecionado", "contatado", "descartado", "cliente"}
    if req.status not in validos:
        raise HTTPException(400, f"status inválido; use um de {sorted(validos)}")
    p = db.query(Prospecto).filter(Prospecto.num_auto == num_auto).first()
    if not p:
        raise HTTPException(404, "Auto não encontrado na carteira.")
    p.status = req.status
    if req.notas is not None:
        p.notas = req.notas
    db.commit()
    return p.to_dict()


# ───────────────────────── Catálogo de auditoria ─────────────────────────
# Fonte única de verdade: o front-end lê os itens daqui em vez de tê-los
# escritos no próprio código (que era onde a duplicação vivia).

@app.get("/api/catalogo")
def obter_catalogo(authorization: Optional[str] = Header(None)):
    _checar_auth(authorization)
    return catalogo.carregar()


class AuditoriaRequest(BaseModel):
    respostas: dict[str, str]              # {"1.1": "ok" | "fail" | "na", ...}
    valorMulta: Optional[str | float] = None  # para calcular a exposição financeira
    casoId: Optional[str] = None           # se informado, o resultado é gravado no caso


@app.post("/api/auditoria")
def executar_auditoria(
    req: AuditoriaRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    _checar_auth(authorization)
    resultado = catalogo.executar_auditoria(req.respostas, req.valorMulta)
    if req.casoId:
        caso = db.query(Caso).filter(Caso.id == req.casoId).first()
        if caso:
            caso.audit_result = resultado
            db.commit()
    return resultado


@app.post("/api/laudo-tecnico")
def emitir_laudo_tecnico(
    req: AuditoriaRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Camada do CONSUMIDOR FINAL — Inteligência Forense.

    Devolve apenas constatações técnicas verificáveis. Nenhuma tese, taxa de
    êxito, citação de jurisprudência ou valor projetado por probabilidade
    trafega por aqui: a separação é feita no servidor, de modo que o aplicativo
    do consumidor nunca chega a receber a camada jurídica.
    """
    _checar_auth(authorization)
    completo = catalogo.executar_auditoria(req.respostas, req.valorMulta)
    if req.casoId:
        caso = db.query(Caso).filter(Caso.id == req.casoId).first()
        if caso:
            caso.audit_result = completo
            db.commit()
    laudo = catalogo.laudo_tecnico(completo)
    # O valor da multa é fato, e acompanha o laudo. O valor projetado por
    # probabilidade de êxito, não — esse fica no anexo jurídico.
    if req.valorMulta:
        laudo["valor_da_multa_em_analise"] = req.valorMulta
    return laudo


@app.post("/api/anexo-juridico")
def emitir_anexo_juridico(req: AuditoriaRequest, authorization: Optional[str] = Header(None)):
    """
    Camada do ADVOGADO constituído pelo cliente — ou uso interno de priorização.
    Qualificação das constatações, teses, fundamentos, taxas e exposição financeira.
    """
    _checar_auth(authorization)
    completo = catalogo.executar_auditoria(req.respostas, req.valorMulta)
    return catalogo.anexo_juridico(completo)


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
