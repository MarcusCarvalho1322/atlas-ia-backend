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


class Notificacao(Base):
    """
    Notificação do IBAMA vinculada ao MESMO PROCESSO do auto.

    POR QUE SÓ O VÍNCULO POR PROCESSO
    ----------------------------------
    Medido no arquivo real: 8,3% dos autos da carteira têm notificação com o
    mesmo NUM_PROCESSO, e 22% têm notificação do mesmo CPF/CNPJ. A tentação é
    usar os 22%. Seria errado: a mesma pessoa pode ter sido notificada noutro
    ano, noutro estado, por outro motivo — exibir isso ao lado de uma pergunta
    sobre a notificação DESTE processo atribuiria ao caso um documento que não
    é dele. Fica só o processo.

    Nos registros que casam por processo a qualidade é alta: data e prazo em
    100%, forma de entrega em 93,5%, e a descrição da exigência em 100% — o que
    o IBAMA cobrou antes de autuar, nas palavras do próprio órgão.

    OS NÚMEROS, COM O DENOMINADOR DE CADA UM
    -----------------------------------------
    Duas contagens diferentes convivem aqui e é preciso não confundi-las. O
    arquivo bruto do IBAMA de 2026 casa por processo com 2.313 notificações em
    2.174 processos distintos; desses, só os autos que sobrevivem ao filtro de
    prospecção chegam à carteira. Na carteira medida (10.762 autos, 9.640 com
    número de processo): 893 autos com notificação — 8,3% da carteira, 9,3%
    dos que têm processo — e 951 pares auto × notificação.

    UMA ARITMÉTICA QUE QUASE VIROU ERRO
    ------------------------------------
    Comparar a lavratura com o vencimento do prazo da notificação parecia
    acusar dois terços dos autos de terem sido lavrados antes de o prazo
    vencer. Era artefato: na carteira, 558 dos 951 pares (58,7%) são do MESMO
    DIA — a mesma fiscalização, com a notificação impondo obrigação futura e o
    auto punindo fato passado. Depois de exigir que o auto venha DEPOIS da
    notificação, o achado real cai para 30 autos (3,4% dos 893 com
    notificação). Outros 46 autos (5,2%) têm auto ANTERIOR à notificação, que
    é apontamento de ordem dos atos, não de prazo. É isso que o sistema mostra,
    e nada além disso.
    """
    __tablename__ = "notificacoes"

    num_notificacao = Column(String, primary_key=True)
    processo = Column(String, index=True, nullable=False)

    dat_notificacao = Column(String, nullable=True)
    prazo_apresentacao = Column(String, nullable=True)
    forma_entrega = Column(String, nullable=True)
    des_ocorrencia = Column(String, nullable=True)       # o que o órgão exigiu
    des_atividade_notificado = Column(String, nullable=True)
    sit_atendida = Column(String, nullable=True)
    sit_conclusao = Column(String, nullable=True)
    sit_auto_lavrado = Column(String, nullable=True)
    nom_municipio = Column(String, nullable=True)
    sig_uf = Column(String, nullable=True)
    num_ordem_fiscalizacao = Column(String, nullable=True)
    unid_ordenadora = Column(String, nullable=True)

    carregado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Termo(Base):
    """
    Termo lavrado na MESMA fiscalização do auto: embargo, apreensão, suspensão
    ou demolição.

    O VÍNCULO AQUI É O PRÓPRIO NÚMERO DO AUTO
    ------------------------------------------
    Diferente da notificação, que só casa pelo processo, o termo traz o
    NUM_AUTO_INFRACAO no próprio registro. É o vínculo mais forte de todas as
    fontes integradas até agora — não há inferência nenhuma entre o termo e o
    auto: o IBAMA declara o par.

    O QUE ISSO ALCANÇA, MEDIDO NA CARTEIRA DE 10.762 AUTOS
    -------------------------------------------------------
      embargo     2.348 termos → 2.346 autos  (21,8% da carteira)
      apreensão     653 termos →   525 autos  ( 4,9%)
      suspensão      21 termos →    17 autos  ( 0,2%)
      demolição       0                       (nenhum auto da carteira)
    Somados: 2.861 autos distintos, 26,6% da carteira. Termos cancelados
    (SIT_CANCELADO = S) são descartados na extração e nunca chegam aqui.

    O ACHADO QUE JUSTIFICA ESTA FONTE
    ----------------------------------
    A área é a base do cálculo da multa de desmatamento, e o cadastro do auto
    a traz em apenas 7,4% da carteira. O embargo da MESMA fiscalização traz
    QTD_AREA_EMBARGADA em 91,5% dos casos. Resultado: 1.444 autos sem área no
    próprio registro têm área no termo de embargo — e 93,2% deles descrevem
    desmatamento ou supressão, exatamente onde o número decide o valor.

    A CONFERÊNCIA QUE AUTORIZA MOSTRAR ESSE NÚMERO
    -----------------------------------------------
    Área de embargo e área autuada são conceitos distintos em tese: o embargo
    interdita para permitir recuperação e poderia ser mais amplo. Por isso a
    comparação foi feita antes de decidir. Nos 703 autos em que as DUAS áreas
    existem, elas são idênticas em 698 (99,3%). Na prática, nesta carteira, é
    o mesmo número publicado duas vezes.

    Daí decorrem as duas consequências que o código respeita:
      1. o número do embargo PREENCHE UMA LACUNA do cadastro, mas não confirma
         nada — é a mesma fonte estatal, não uma medição independente;
      2. quando as duas áreas existem e DIVERGEM (5 casos, 0,7%), o próprio
         Estado publicou dois números para o mesmo auto. Isso é exibido lado a
         lado, como evidência, e continua sendo a pessoa quem decide.

    NENHUM APURADO NOVO
    --------------------
    Seria tentador transformar a divergência de áreas em resposta automática.
    Não vira: o item 4.9 pergunta questão jurídica, não "os dois números são
    diferentes". A fonte 4 acrescenta evidência e nada além disso.

    UMA OBSERVAÇÃO DE DATA QUE, DESTA VEZ, NÃO É ARMADILHA
    -------------------------------------------------------
    2.298 dos 2.348 embargos (97,9%) são do MESMO DIA do auto. Na notificação
    o mesmo dia servia para DESCARTAR um achado falso; aqui ele serve para o
    contrário: confirma que termo e auto documentam a mesma fiscalização, que
    é justamente o que autoriza ler a área do termo ao lado da do auto.
    """
    __tablename__ = "termos"

    num_termo = Column(String, primary_key=True)
    tipo = Column(String, index=True, nullable=False)     # embargo|apreensao|suspensao|demolicao
    num_auto = Column(String, index=True, nullable=False)

    data = Column(String, nullable=True)
    municipio = Column(String, nullable=True)
    uf = Column(String, nullable=True)
    area = Column(String, nullable=True)                  # QTD_AREA_EMBARGADA, em hectares
    tipo_area = Column(String, nullable=True)             # Desmatamento | Atividade | ...
    sit_desembargo = Column(String, nullable=True)
    dat_desembargo = Column(String, nullable=True)
    des_desembargo = Column(String, nullable=True)
    descricao = Column(String, nullable=True)             # o que o termo determina
    localizacao = Column(String, nullable=True)
    forma_entrega = Column(String, nullable=True)
    justificativa = Column(String, nullable=True)
    valor = Column(String, nullable=True)                 # apreensão / demolição
    num_ordem_fiscalizacao = Column(String, nullable=True)
    unid_ordenadora = Column(String, nullable=True)

    carregado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Julgamento(Base):
    """
    Desfecho do auto no SICAFI — a única base que diz se o caso ainda está vivo.

    COBERTURA BAIXA, VALOR DE OUTRA NATUREZA
    -----------------------------------------
    O arquivo tem 261.976 julgamentos das 27 UFs, mas só 38 autos da carteira
    aparecem nele — 0,4%. A razão é estrutural e não vai melhorar: a carteira é
    de autos de 2026, e auto novo ainda não foi julgado.

    Mesmo assim entra, porque desses 38, TRINTA E UM JÁ ESTÃO QUITADOS. São
    leads mortos: alguém da equipe ligaria para oferecer defesa de uma multa
    que o autuado já pagou. Nenhuma outra base revela isso, e o constrangimento
    acontece na frente do prospecto.

    Então esta tabela não é fonte de evidência para o protocolo. É filtro de
    carteira: serve para NÃO abordar quem não tem mais o problema.

    UMA COLUNA QUE EXIGE CUIDADO
    -----------------------------
    Valor do Auto e Valor Pago usam vírgula como separador de MILHAR e de
    DECIMAL no mesmo campo: "1,000" é mil, "353,5" é trezentos e cinquenta e
    três e meio, "3,854,3" é três mil oitocentos e cinquenta e quatro e três.
    Guardados como texto, exatamente como vieram. Quem for fazer conta com eles
    decodifica pelo tamanho do último grupo — e antes disso filtra a moeda,
    porque há valores em Cruzeiro, Cruzado e BTN que não são comparáveis a Real.
    """
    __tablename__ = "julgamentos"

    num_auto = Column(String, primary_key=True)
    status_debito = Column(String, index=True, nullable=True)
    decisao = Column(String, nullable=True)
    dat_julg_principal = Column(String, nullable=True)
    dat_julg_recurso = Column(String, nullable=True)
    valor_auto = Column(String, nullable=True)      # texto cru: ver nota acima
    moeda = Column(String, nullable=True)
    valor_pago = Column(String, nullable=True)      # texto cru: ver nota acima
    dat_pagamento = Column(String, nullable=True)

    carregado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AutoEmUC(Base):
    """
    Auto cuja coordenada cai dentro de Unidade de Conservação federal.

    GEOMETRIA, NÃO TEXTO
    ---------------------
    Esta é a primeira fonte do sistema que não casa por número nem por
    documento: casa por POSIÇÃO. A coordenada do auto é testada contra os 347
    polígonos das UCs federais publicados pelo ICMBio (camada
    `limiteucsfederais_a` do geoserviço da INDE, agosto de 2026).

    O cruzamento é feito FORA e só o resultado entra aqui, por uma razão
    prática: o Postgres de produção não tem extensão geoespacial, e carregar
    44 MB de polígonos para refazer a conta a cada consulta seria desperdício.
    O par auto → UC é estável; refazer só quando o ICMBio republicar a camada.

    O QUE FOI MEDIDO
    -----------------
    97,8% da carteira tem coordenada aproveitável. Dentro de UC federal: 194
    autos (1,8%) — 168 em Uso Sustentável e 26 em PROTEÇÃO INTEGRAL.

    Os 26 são o motivo desta tabela existir. Parque Nacional, Reserva
    Biológica e Estação Ecológica não admitem as mesmas atividades que uma APA,
    e isso muda tipificação e competência. Hoje o analista só descobre lendo o
    processo — se descobrir.

    O LIMITE, QUE VAI ESCRITO NA EVIDÊNCIA
    ---------------------------------------
    O ponto testado é a coordenada que o IBAMA registrou no auto, não o
    perímetro da área autuada. Ponto dentro do polígono não prova que toda a
    área está dentro, nem ponto fora prova que nada está. E zona de
    amortecimento NÃO está nesta camada — ausência aqui não é ausência de UC
    por perto.
    """
    __tablename__ = "autos_em_uc"

    num_auto = Column(String, primary_key=True)
    nome_uc = Column(String, index=True, nullable=True)
    cnuc = Column(String, nullable=True)
    grupo = Column(String, index=True, nullable=True)   # Protecao Integral | Uso Sustentavel
    esfera = Column(String, nullable=True)
    bioma = Column(String, nullable=True)
    ano_criacao = Column(String, nullable=True)
    ato_criacao = Column(String, nullable=True)

    carregado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Autorizacao(Base):
    """
    Autorização de supressão de vegetação do Sinaflor, do CNPJ autuado.

    O ITEM QUE ISTO ALCANÇA É DETERMINANTE E CHEGA VAZIO
    -----------------------------------------------------
    O item 2.1 pergunta se havia autorização vigente antes da autuação. É de
    peso 10 no protocolo e hoje chega ao analista completamente em branco:
    nenhuma base que o sistema lia respondia a isso.

    O VÍNCULO É PELO CNPJ, E ISSO EXIGE UMA RESSALVA QUE NÃO PODE SUMIR
    -------------------------------------------------------------------
    Diferente do termo, que traz o número do auto, aqui o vínculo é o CNPJ do
    detentor. Uma autorização do mesmo CNPJ NÃO é necessariamente a
    autorização deste fato: pode ser de outro imóvel, outro município, outro
    período. Por isso nada aqui vira resposta — vira evidência, com a janela
    de validade e o município ao lado, para a pessoa comparar.

    Só casa CNPJ de 14 dígitos. A carteira tem 2.110 CNPJs contra 3.308
    documentos mascarados de pessoa física, e o CPF vem mascarado dos dois
    lados: pessoa física fica de fora, e é melhor ficar de fora do que casar
    errado.

    O QUE FOI MEDIDO
    -----------------
    604 autorizações, 54 CNPJs, alcançando 208 autos (1,9% da carteira).
    Situação: 357 emitidas, 239 vencidas, 8 suspensas. A distinção importa —
    autuado que TINHA autorização e ela venceu é um caso; autuado que nunca
    teve é outro, e são defesas diferentes.

    POR QUE A CHAVE NÃO É O NÚMERO DA AUTORIZAÇÃO
    ----------------------------------------------
    Parecia óbvio que fosse, e o primeiro teste mostrou que não: das 604 linhas
    só 551 números são distintos. Ao abrir os repetidos, a razão apareceu — o
    arquivo publica UMA LINHA POR IMÓVEL, e uma autorização pode cobrir vários.
    A autorização 10539201905317, por exemplo, vem quatro vezes, com dois
    imóveis diferentes.

    Chavear pelo número sozinho descartaria silenciosamente os demais imóveis
    de cada autorização — e imóvel é justamente o campo que permite dizer se a
    autorização tem a ver com ESTE fato. Perder isso esvaziaria a evidência.

    Daí o `id` determinístico: número + assinatura curta do imóvel. Recarregar
    o mesmo arquivo produz os mesmos ids, então a carga continua idempotente;
    linhas idênticas (34 dos 46 casos) colapsam, como devem; linhas que diferem
    no imóvel sobrevivem separadas, como devem.
    """
    __tablename__ = "autorizacoes"

    id = Column(String, primary_key=True)               # nro#assinatura-do-imovel
    nro_autorizacao = Column(String, index=True, nullable=False)
    cnpj = Column(String, index=True, nullable=False)
    data_emissao = Column(String, nullable=True)
    data_validade = Column(String, nullable=True)
    situacao = Column(String, index=True, nullable=True)
    uf = Column(String, nullable=True)
    municipio = Column(String, nullable=True)
    atividade = Column(String, nullable=True)
    finalidade = Column(String, nullable=True)
    area_total = Column(String, nullable=True)
    imovel = Column(String, nullable=True)
    car = Column(String, nullable=True)
    orgao_analise = Column(String, nullable=True)
    bioma = Column(String, nullable=True)

    carregado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Acesso(Base):
    """
    Quem consultou qual caso, e quando.

    POR QUE ISTO EXISTE
    --------------------
    A autenticação já identificava a pessoa: `_checar_auth` devolve o nome de
    quem entrou, lido do mapa senha → nome. Só que nenhuma rota guardava esse
    nome — ele era calculado e descartado na mesma linha. O sistema sabia quem
    estava ali e esquecia no instante seguinte.

    Num sistema que manipula caso de cliente, com advogada sócia e equipe com
    senhas individuais, isso é uma lacuna concreta: no dia em que alguém
    perguntar "quem acessou este processo", a resposta seria "não sei". Não é
    hipótese remota — é a primeira pergunta de qualquer apuração, interna ou
    externa, e a única resposta aceitável é um registro que já existia antes
    da pergunta.

    O QUE ENTRA, E O QUE DELIBERADAMENTE NÃO ENTRA
    -----------------------------------------------
    Entra o mínimo que responde à pergunta: quem, o que fez, sobre qual caso,
    quando. NÃO entra endereço IP, agente do navegador nem qualquer coisa que
    transforme um registro de auditoria num rastreamento da equipe. O objetivo
    é responder por um caso, não vigiar quem trabalha nele.

    Também não entra o conteúdo: o registro diz que fulano emitiu laudo do auto
    X, não o que o laudo dizia. O laudo já é guardado em outro lugar.
    """
    __tablename__ = "acessos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quem = Column(String, index=True, nullable=False)     # nome vindo do mapa de senhas
    acao = Column(String, index=True, nullable=False)     # consultou | emitiu-laudo | ...
    alvo = Column(String, index=True, nullable=True)      # num_auto ou id do caso
    em = Column(DateTime, index=True, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {"id": self.id, "quem": self.quem, "acao": self.acao,
                "alvo": self.alvo, "em": self.em.isoformat() if self.em else None}


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


class AutoIcmbio(Base):
    """
    Auto de infração lavrado pelo ICMBio, do CNPJ autuado.

    POR QUE ISTO EXISTE
    -------------------
    O IBAMA não publica auto do ICMBio: são órgãos diferentes. O geoserviço da
    INDE publica 41.839 deles, com número do auto, valor, artigo enquadrado,
    termos de embargo e apreensão, processo e situação de julgamento — e, ao
    contrário da carteira do IBAMA, com histórico que vai de 2008 a 2026.

    É esse histórico que importa. O item 5.3 pergunta por reincidência, que
    exige autuação ANTERIOR, e até aqui o sistema só sabia comparar autos de
    2026 entre si. O item 2.2 pergunta por autuação paralela de outro órgão
    sobre o mesmo fato, e nenhuma base respondia.

    O QUE FOI DEIXADO DE FORA, DE PROPÓSITO
    ---------------------------------------
    O ICMBio publica CPF COMPLETO, sem máscara, em 33.269 dos 41.839 registros,
    e o NOME COMPLETO do autuado em todos eles. O IBAMA não faz isso — mascara
    o documento —, e este sistema também não faz.

    Então nem o nome nem o CPF atravessam a extração. Não chegam ao arquivo,
    não chegam ao banco, não chegam à tela. Entram apenas os 3.086 registros de
    PESSOA JURÍDICA, e sem o nome: o CNPJ basta para o cruzamento, e guardar
    dado pessoal que não é necessário seria criar exposição sem finalidade.
    A decisão é a mesma do Sinaflor, por razão adicional.

    O VÍNCULO É O CNPJ, NÃO O NÚMERO DO AUTO
    ----------------------------------------
    Auto do ICMBio do mesmo CNPJ não é, necessariamente, sobre o mesmo fato do
    auto do IBAMA em análise. Pode ser outro imóvel, outro estado, outro ano.
    Por isso nada aqui vira resposta: vira evidência, com data, município e
    unidade de conservação ao lado, e com a ressalva escrita.

    A CHAVE É COMPOSTA
    ------------------
    O número do auto se repete 22 vezes no arquivo, para fatos distintos —
    mesmo número, anos e municípios diferentes. Chavear só pelo número
    descartaria o outro fato em silêncio, que foi exatamente o defeito que o
    teste pegou no Sinaflor. A chave é número + assinatura de data, município e
    processo.
    """
    __tablename__ = "autos_icmbio"

    id = Column(String, primary_key=True)                 # numero#assinatura
    num_auto_icmbio = Column(String, index=True, nullable=False)
    cnpj = Column(String, index=True, nullable=False)
    data = Column(String, nullable=True)
    ano = Column(String, index=True, nullable=True)
    valor_multa = Column(String, nullable=True)
    tipo = Column(String, nullable=True)
    tipo_infracao = Column(String, nullable=True)
    artigo_1 = Column(String, nullable=True)
    artigo_2 = Column(String, nullable=True)
    nome_uc = Column(String, nullable=True)
    cnuc = Column(String, nullable=True)
    municipio = Column(String, nullable=True)
    uf = Column(String, nullable=True)
    termos_embargo = Column(String, nullable=True)
    termos_apreensao = Column(String, nullable=True)
    ordem_fiscalizacao = Column(String, nullable=True)
    processo = Column(String, nullable=True)
    julgamento = Column(String, nullable=True)
    tem_embargo = Column(String, nullable=True)
    tem_apreensao = Column(String, nullable=True)
    carregado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AlertaDeter(Base):
    """
    Alerta de desmatamento do DETER/INPE próximo ao ponto do auto — item 4.1.

    O ITEM E O PONTO CEGO
    ---------------------
    O item 4.1 pergunta se as imagens que embasaram a autuação têm data, sensor
    e resolução documentados. Até aqui o sistema não tinha nada a mostrar: o
    cadastro do auto não fala das imagens. O INPE publica os alertas com
    `view_date`, `sensor` e `satellite` — exatamente os metadados que o item
    manda conferir.

    O RECORTE FOI MEDIDO, NÃO ESCOLHIDO NO OLHO
    -------------------------------------------
    Varri os 10.520 autos com coordenada contra as camadas do DETER. O
    resultado mostra por que proximidade sozinha não serve:

        alerta a até 2 km, sem olhar data ...... 56,9%   ruído
        a até 300 m, sem olhar data ............ 17,4%
        a até 500 m E até 180 dias antes ....... 2,50%   sinal
        a até 300 m E até 180 dias antes ....... 1,70%

    Na Amazônia há alerta em quase toda parte na escala de quilômetros. É a
    combinação de espaço apertado com tempo compatível que separa o que pode
    ser o alerta daquele fato do que é só vizinhança.

    O recorte gravado é 500 m e 180 dias: 263 autos, mediana de 238 metros e
    54 dias entre o alerta e o fato, 90% classificados como corte raso.

    O QUE ISTO NÃO PROVA
    --------------------
    Proximidade não é identidade. Este NÃO é necessariamente o alerta que o
    processo cita — é um alerta público compatível em espaço e tempo. Serve
    para conferir contra o que o processo alega, e a distância em metros e a
    diferença em dias vão escritas na tela para a pessoa julgar.

    E o DETER é sistema de ALERTA RÁPIDO para orientar fiscalização, não de
    medição: o próprio INPE trata o PRODES como o dado oficial de taxa. Área de
    alerta do DETER não é medida de área autuada, e a evidência diz isso.
    """
    __tablename__ = "alertas_deter"

    id = Column(String, primary_key=True)                # num_auto#ordem
    num_auto = Column(String, index=True, nullable=False)
    camada = Column(String, nullable=True)               # deter-amz | deter-cerrado-nb
    view_date = Column(String, nullable=True)            # data do alerta
    dias_antes = Column(Integer, nullable=True)          # entre o alerta e o fato
    metros = Column(Integer, nullable=True)              # do ponto do auto ao alerta
    classname = Column(String, nullable=True)
    sensor = Column(String, nullable=True)
    satellite = Column(String, nullable=True)
    path_row = Column(String, nullable=True)
    municipality = Column(String, nullable=True)
    uf = Column(String, nullable=True)
    carregado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CoberturaMapbiomas(Base):
    """
    O que a base de referência via naquele ponto no ano ANTERIOR ao fato — item 4.6.

    O ITEM
    ------
    4.6 pergunta se a classificação da vegetação está correta: primária ou
    secundária, e qual tipologia. É o item que decide enquadramento e
    dosimetria — "objeto de especial preservação" (art. 50 do Decreto 6.514) e
    o regime da Lei 11.428 para a Mata Atlântica dependem do estágio. Até aqui
    o sistema não tinha o que mostrar: o cadastro do auto não traz campo de
    tipologia nem de estágio.

    AS DUAS CAMADAS, COM LEGENDA CONFERIDA NA FONTE
    -----------------------------------------------
    MapBiomas Brasil, Coleção 11, 30 m, dois produtos distintos:

      cobertura .... brazil_coverage-col11_{ano}.tif
                     Legenda oficial em CSV (legend_code_..._collection_11.csv),
                     33 classes. 3 = Formação Florestal, 15 = Pastagem,
                     24 = Área Urbanizada, 30 = Mineração, 39 = Soja...

      primária x    deforestation_secondary_vegetation-brazil_classification_{ano}.tif
      secundária    1 Antrópico · 2 Vegetação Primária · 3 Vegetação Secundária
                    4 Supressão de Veg. Primária · 5 Recuperação para veg.
                    secundária · 6 Supressão de Veg. Secundária
                    7 Outras transições · 0 = sem dado

    A segunda legenda NÃO tem arquivo publicado na página de Códigos de
    Legenda, e o Apêndice do ATBD nomeia as sete classes mas não dá os códigos
    numéricos. Os códigos acima foram lidos no texto da própria página do
    produto do MapBiomas em 17/09/2026, e depois conferidos contra a cobertura
    ponto a ponto: onde a cobertura diz Mineração a camada diz Antrópico, onde
    diz Formação Florestal diz Vegetação Primária. Duas fontes independentes
    concordando é o que autorizou usar a camada. Sem isso ela ficaria de fora,
    como ficaram o INCRA e o item 2.5.

    POR QUE UMA JANELA DE 5 x 5 E NÃO UM PIXEL
    ------------------------------------------
    O auto informa um PONTO (DS_WKT), não o polígono da área. Ler um pixel de
    30 m e apresentá-lo como "a vegetação da área" seria trocar uma coisa pela
    outra. Grava-se a classe do pixel central E a moda dos 25 pixels de 150 m x
    150 m em volta, com quantos dos 25 são da mesma classe. Ponto no meio de
    uma mancha homogênea (25/25) e ponto na borda (13/25) não valem o mesmo, e
    quem lê precisa ver a diferença.

    A GEOMETRIA DO AUTO É COMPATÍVEL COM O MUNICÍPIO QUE O AUTO DECLARA?
    -------------------------------------------------------------------
    Esta pergunta nasceu de um número que parecia errado: 44% dos pontos da
    carteira caem em "Área Urbanizada". Investigado, não era defeito da
    leitura — são autos de Fauna, Pesca, Cadastro Técnico e Administração
    Ambiental, que acontecem em cidade mesmo. Mas a investigação achou outra
    coisa: 1.022 autos (9,5%) têm geometria FORA do município que o próprio
    auto declara, e 122 deles a mais de 1.000 km — inclusive 47 autos de Novo
    Progresso/PA cuja coordenada cai na sede do IBAMA em Brasília.

    Isso é evidência do item 1.10 por si só. E é GATE: onde a geometria não
    cai no município declarado, a leitura de vegetação não é apresentada.
    Verificação que não aconteceu não pode parecer que aconteceu.

    Malha municipal: IBGE, API de Malhas v3, qualidade intermediária, 5.570
    polígonos, baixada em 17/09/2026. Nas bordas o traçado tem imprecisão de
    centenas de metros — por isso grava-se a distância em km, e não um "sim ou
    não".
    """
    __tablename__ = "cobertura_mapbiomas"

    num_auto = Column(String, primary_key=True)
    ano_ref = Column(Integer, nullable=True)          # ano do fato menos 1

    cob_centro = Column(Integer, nullable=True)       # código da classe no pixel
    cob_classe = Column(String, nullable=True)        # nome da classe (legenda oficial)
    cob_moda = Column(Integer, nullable=True)         # classe mais frequente na janela
    cob_moda_classe = Column(String, nullable=True)
    cob_homog = Column(Integer, nullable=True)        # pixels da moda, de 25

    veg_centro = Column(Integer, nullable=True)       # 1..7 (primária x secundária)
    veg_classe = Column(String, nullable=True)
    veg_moda = Column(Integer, nullable=True)
    veg_moda_classe = Column(String, nullable=True)
    veg_homog = Column(Integer, nullable=True)

    mun_situacao = Column(String, nullable=True)      # DENTRO | FORA | NAO_LOCALIZADO
    mun_km = Column(Float, nullable=True)             # da borda do município ao ponto
    conduta = Column(String, nullable=True)           # supressao | regeneracao | outra

    carregado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))
