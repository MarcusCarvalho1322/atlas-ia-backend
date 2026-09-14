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

    # O recorte útil do registro público, guardado cru. A base do IBAMA tem 84
    # colunas e o sistema lia 15; as outras carregam o enquadramento legal, a
    # dosimetria, a forma de entrega da notificação, a área autuada e os marcos
    # de prescrição — justamente o que o protocolo de 60 itens pergunta.
    #
    # Guardado como JSON, e não em colunas novas, de propósito: o dicionário de
    # campos do IBAMA muda sem aviso, e uma coluna por campo transformaria cada
    # mudança da fonte numa migração de banco. Aqui um campo novo simplesmente
    # aparece no dicionário. Só chaves com valor entram — o que não veio da
    # fonte não existe, em vez de existir vazio.
    registro = Column(JSON, nullable=True)
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


class DividaAtiva(Base):
    """
    Perfil do AUTUADO na Dívida Ativa da União — não da multa deste auto.

    ESTA DISTINÇÃO É O PONTO INTEIRO DESTA TABELA.

    A PGFN publica trimestralmente 9 GB de inscrições em dívida ativa, com 134
    receitas distintas. Varri as 134: NENHUMA identifica multa do IBAMA. Há uma
    chamada "Contribuição Risco Ambiental/Aposentadoria Especial" que parece
    ambiental e é previdenciária (SAT/RAT) — um casamento por palavra-chave
    produziria aqui exatamente o erro de aparência plausível que este sistema
    existe para não cometer.

    Ou seja: não dá para amarrar a multa de um auto à sua inscrição em dívida
    ativa. O que dá, e vale muito, é o PERFIL DE ENDIVIDAMENTO FEDERAL do
    autuado — se já está em execução fiscal, se há corresponsável registrado,
    se tem parcelamento em curso. Isso pesa nos itens 6.3, 7.4, 7.5 e 7.6 como
    evidência, e reordena a carteira comercial.

    Só pessoa jurídica. O CPF da PGFN vem mascarado em posições diferentes das
    que o IBAMA publica — a sobreposição é de dois dígitos, e cruzar por isso
    seria inventar correspondência.
    """
    __tablename__ = "divida_ativa"

    # 14 dígitos, só números — a mesma forma que Prospecto.cnpj usa.
    cnpj = Column(String, primary_key=True)
    # Os 8 primeiros dígitos identificam o GRUPO ECONÔMICO. A PGFN publica por
    # estabelecimento: a dívida da matriz não está na linha da filial. Um auto
    # lavrado contra a filial não casa com a matriz no CNPJ inteiro — daí a
    # raiz existir, para uma segunda tentativa que a evidência rotula como
    # sendo do grupo, nunca daquele estabelecimento.
    raiz = Column(String, index=True, nullable=True)
    nome = Column(String, nullable=True)
    uf = Column(String, nullable=True)

    inscricoes = Column(Integer, default=0)
    valor_total = Column(Float, default=0.0)
    ajuizadas = Column(Integer, default=0)
    corresponsavel = Column(Integer, default=0)
    solidario = Column(Integer, default=0)

    situacoes = Column(JSON, nullable=True)            # {"Em cobrança": 12, ...}
    receitas_principais = Column(JSON, nullable=True)  # as 5 mais frequentes
    inscricao_mais_antiga = Column(String, nullable=True)
    inscricao_mais_recente = Column(String, nullable=True)

    # Data da extração e referência da base. Vai junto em toda evidência: uma
    # ausência aqui só significa ausência NAQUELE trimestre.
    referencia_da_base = Column(String, nullable=True)
    carregado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {c.name: (getattr(self, c.name).isoformat()
                         if c.name == "carregado_em" and getattr(self, c.name) else getattr(self, c.name))
                for c in self.__table__.columns}


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
