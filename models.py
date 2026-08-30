"""
Modelo de dados do caso ATLAS-IA.

Espelha exatamente a estrutura que hoje vive só no localStorage do
navegador (ver App.jsx: `salvarCaso`/`carregarCaso`), para que a migração
do front-end seja só trocar "onde" o caso é salvo — nenhum campo muda de
nome ou de formato.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON, Integer, Float
from db import Base


def _new_id() -> str:
    # Mesmo formato curto que o front-end já gera hoje com Date.now().toString(36)
    return uuid.uuid4().hex[:12]


class Caso(Base):
    __tablename__ = "casos"

    id = Column(String, primary_key=True, default=_new_id)
    form_data = Column(JSON, nullable=False)      # espelha formData do App.jsx
    audit_result = Column(JSON, nullable=True)    # espelha auditResult do App.jsx (pode ser null)
    geo_verificacoes = Column(JSON, nullable=True)  # histórico de checagens de satélite feitas para este caso
    saved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "formData": self.form_data,
            "auditResult": self.audit_result,
            "geoVerificacoes": self.geo_verificacoes or [],
            "savedAt": self.saved_at.isoformat() if self.saved_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class Prospecto(Base):
    """
    Caso identificado na base pública do IBAMA e acompanhado pela prospecção.

    Existe para responder duas perguntas que a base bruta não responde:
    o que apareceu HOJE que não existia ontem, e em que pé está a abordagem
    de cada caso. Sem isso a rotina diária vira só uma releitura da mesma
    lista, e casos com prazo correndo passam batido.
    """
    __tablename__ = "prospectos"

    num_auto = Column(String, primary_key=True)
    processo = Column(String, nullable=True)
    valor = Column(Float, nullable=True)
    uf = Column(String, index=True, nullable=True)
    municipio = Column(String, nullable=True)
    bioma = Column(String, nullable=True)
    tipo_infracao = Column(String, nullable=True)
    tipo_pessoa = Column(String, nullable=True)
    documento_mascarado = Column(String, nullable=True)
    # CNPJ é identificador empresarial público — a Receita publica o cadastro
    # inteiro. Guardado por extenso para permitir a consulta de contato.
    # CPF NÃO é guardado por extenso: para pessoa física fica só o mascarado.
    cnpj = Column(String, index=True, nullable=True)
    nome = Column(String, nullable=True)

    dt_fato = Column(String, nullable=True)
    dt_auto = Column(String, nullable=True)
    dt_ciencia = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)

    sinais = Column(JSON, nullable=True)
    prioridade = Column(Float, index=True, default=0.0)
    dias_para_defesa = Column(Integer, nullable=True)

    # Acompanhamento comercial
    status = Column(String, index=True, default="novo")   # novo|selecionado|contatado|descartado|cliente
    notas = Column(String, nullable=True)

    visto_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))      # primeira aparição
    atualizado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self, revelar_documento=False):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        for k in ("visto_em", "atualizado_em"):
            d[k] = d[k].isoformat() if d[k] else None
        if not revelar_documento:
            d.pop("nome", None)
        return d


class CacheConsulta(Base):
    """
    Cache de consultas a fontes externas.

    Mesmo princípio da `scrapingCache` do SafraCheck: guarda a resposta com a
    data em que foi buscada, para não repetir consulta desnecessária nem
    depender da fonte estar no ar a cada abertura de tela.
    """
    __tablename__ = "cache_consultas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    origem = Column(String, index=True, nullable=False)   # ex.: "receita_cnpj"
    chave = Column(String, index=True, nullable=False)    # ex.: o CNPJ
    resultado = Column(JSON, nullable=True)
    buscado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expira_em = Column(DateTime, nullable=True)
