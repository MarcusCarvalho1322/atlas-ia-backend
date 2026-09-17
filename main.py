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
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional, Any

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import Base, engine, get_db, SessionLocal, descrever_banco, garantir_colunas
from models import Caso, Prospecto, DividaAtiva, Notificacao, Termo, Acesso
import geo_service
import ai_service
import catalogo
import prospeccao
import rotina
import enriquecimento
import preverificacao

Base.metadata.create_all(bind=engine)
# create_all cria tabelas que faltam e não toca nas que já existem. Coluna nova
# em tabela antiga precisa disto — ver a justificativa em db.garantir_colunas.
COLUNAS_ACRESCENTADAS = garantir_colunas()

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]


# ─────────────────────── Acesso: uma senha POR PESSOA ───────────────────────
#
# ATLAS_API_TOKEN     — senha única, herdada. Continua valendo (nada quebra).
# ATLAS_API_TOKENS    — uma por pessoa, no formato  nome:senha,nome:senha
#
# Uma senha compartilhada por toda a equipe tem dois defeitos que só aparecem
# quando já é tarde: não há como saber QUEM fez o quê, e tirar o acesso de uma
# pessoa obriga a trocar a senha de todo mundo. Com senha nomeada, revogar é
# apagar uma entrada — os demais nem percebem.
APP_API_TOKEN = os.getenv("ATLAS_API_TOKEN", "")


def _carregar_tokens() -> dict[str, str]:
    """Mapa senha -> nome de quem a usa. O nome nunca sai em resposta de erro."""
    mapa: dict[str, str] = {}
    if APP_API_TOKEN:
        mapa[APP_API_TOKEN] = "senha-mestra"
    for parte in os.getenv("ATLAS_API_TOKENS", "").split(","):
        parte = parte.strip()
        if not parte or ":" not in parte:
            continue
        nome, _, senha = parte.partition(":")
        nome, senha = nome.strip(), senha.strip()
        if nome and senha:
            mapa[senha] = nome
    return mapa


TOKENS = _carregar_tokens()

app = FastAPI(title="ATLAS-IA · atlas-geo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _checar_auth(authorization: Optional[str]) -> str:
    """
    Valida a senha e devolve o nome de quem entrou.

    A mensagem de erro é sempre a mesma, sem dizer se a senha existe, expirou ou
    está só malformada — informação de a mais aqui só ajuda quem está tentando
    adivinhar.
    """
    if not TOKENS:
        return "sem-autenticacao"  # só para teste local; em produção nunca
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Token inválido ou ausente")
    nome = TOKENS.get(authorization[7:].strip())
    if not nome:
        raise HTTPException(401, "Token inválido ou ausente")
    return nome


def _registrar(db, quem: str, acao: str, alvo: Optional[str] = None) -> None:
    """
    Grava quem consultou qual caso.

    NUNCA DERRUBA A ROTA QUE ESTÁ REGISTRANDO. Um registro de acesso é
    importante, mas não é mais importante que a pessoa conseguir trabalhar: se
    a gravação falhar — banco fora do ar, tabela ainda não criada, o que for —
    a exceção é engolida e a rota segue. O contrário produziria a pior das
    combinações: o sistema parando de funcionar por causa do mecanismo que
    existe só para observá-lo.

    A gravação é feita ANTES do trabalho da rota, justamente para que o
    registro exista mesmo que o trabalho falhe depois: consulta que deu erro
    também é consulta, e é a que mais interessa numa apuração.
    """
    if db is None or not quem:
        return
    try:
        db.add(Acesso(quem=quem, acao=acao, alvo=(alvo or None)))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


# ───────────────────────── saúde / info ─────────────────────────
@app.get("/")
def root():
    return {
        "service": "ATLAS-IA · atlas-geo",
        "checks": {
            "anthropic_key_set": bool(ai_service.ANTHROPIC_API_KEY),
            "auth_required": bool(TOKENS),
            "acessos_configurados": len(TOKENS),
            # Sem isto não há como distinguir, de fora, um Postgres vinculado
            # de um SQLite efêmero: os dois respondem 200 em tudo.
            "banco": descrever_banco(),
        },
    }


@app.get("/health")
def health():
    return {"ok": True}


APP_HTML = Path(__file__).parent / "web" / "atlas.html"


@app.get("/app")
@app.get("/console")
def console():
    """
    Serve o front-end único.

    Eram duas telas: o console de prospecção, na nuvem, e o aplicativo de
    análise, que só rodava no computador de uma pessoa por linha de comando.
    Quem não é desenvolvedor nunca abriria o segundo — então, na prática,
    metade do sistema não existia para a equipe. Agora é uma página só, com
    entrada por senha, e as duas coisas viram abas dela.

    /console continua valendo porque é o endereço que a equipe já recebeu.

    A página não guarda segredo nenhum: o endereço e a senha são digitados por
    quem abre e ficam no navegador dele. Sem senha válida, nenhuma rota de
    dados responde — e a camada jurídica vive noutra rota, que este front-end
    não chama.
    """
    if not APP_HTML.exists():
        raise HTTPException(404, "Front-end não encontrado nesta instalação.")
    # Sem Cache-Control, o navegador aplica cache heurístico: guarda a página
    # por conta própria e pode servi-la do disco SEM perguntar ao servidor. Na
    # prática, alguém da equipe continuava vendo uma versão antiga do console
    # depois de uma correção já publicada — e não havia como saber disso pela
    # tela. "no-cache" não proíbe guardar; obriga a revalidar a cada abertura,
    # o que com o ETag custa um 304 e nada de banda.
    # O carimbo de versão é injetado aqui, a partir da data do próprio arquivo.
    # Sem ele, "está atualizado?" só se responde abrindo o código — e a pergunta
    # apareceu toda vez que alguém relatou um problema já corrigido.
    from datetime import datetime, timezone, timedelta
    from fastapi.responses import HTMLResponse

    carimbo = datetime.fromtimestamp(
        APP_HTML.stat().st_mtime, tz=timezone.utc
    ).astimezone(timezone(timedelta(hours=-3))).strftime("%d/%m %Hh%M")

    html = APP_HTML.read_text(encoding="utf-8").replace("{{VERSAO}}", carimbo)
    return HTMLResponse(
        html,
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


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
    """
    Casos do ano, em cache de processo.

    Se o CSV não estiver no disco, baixa sozinho. Isso importa porque o disco
    de um container é efêmero na maioria das plataformas: depois de um
    reinício o arquivo some, e sem isso o ranking passaria a responder 404 até
    alguém perceber e disparar a atualização à mão.
    """
    if ano not in _cache_casos:
        arq = Path(BASE_IBAMA) / f"auto_infracao_{ano}.csv"
        if not arq.exists():
            try:
                prospeccao.baixar_base(BASE_IBAMA, [ano])
            except Exception as e:
                raise HTTPException(502, f"Base de {ano} ausente e o download falhou: {e}")
            if not arq.exists():
                raise HTTPException(404, f"O pacote do IBAMA não contém dados de {ano}.")
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
    _registrar(db, _checar_auth(authorization), "consultou-contato", num_auto)
    p = db.query(Prospecto).filter(Prospecto.num_auto == num_auto).first()
    if not p:
        raise HTTPException(404, "Auto não encontrado na carteira.")
    return {"num_auto": p.num_auto, "contato": enriquecimento.contato_do_caso(db, p)}


# ───────────────────── Pré-verificação do protocolo ─────────────────────

@app.get("/api/prospeccao/{num_auto}/pre-verificacao")
def pre_verificacao_do_caso(num_auto: str, authorization: Optional[str] = Header(None),
                            db: Session = Depends(get_db)):
    """
    O que o registro público já responde do protocolo, antes de alguém digitar.

    Devolve duas coisas separadas de propósito:

      `apurados`    itens resolvidos por conta de chegada sobre dado presente —
                    subtração de datas e cruzamento da carteira. Viram resposta,
                    marcados como apurados, nunca confundidos com o que a pessoa
                    respondeu.

      `evidencias`  o campo do registro e o valor, ao lado da pergunta. O
                    sistema não responde: mostra o fato e devolve o juízo a
                    quem analisa.

    Os irmãos do item 5.6 saem de uma consulta ao acervo, e é por isso que ela
    fica aqui e não dentro do módulo: o cruzamento precisa do banco.
    """
    _registrar(db, _checar_auth(authorization), "consultou-caso", num_auto)
    p = db.query(Prospecto).filter(Prospecto.num_auto == num_auto).first()
    if not p:
        raise HTTPException(404, "Auto não encontrado na carteira.")

    # Autos do mesmo documento. O mascarado basta para agrupar e não expõe
    # documento por extenso de pessoa física.
    familia: list = []
    chave = p.cnpj or p.documento_mascarado
    if chave:
        q = db.query(Prospecto)
        q = q.filter(Prospecto.cnpj == p.cnpj) if p.cnpj else \
            q.filter(Prospecto.documento_mascarado == p.documento_mascarado)
        familia = [x for x in q.limit(200).all() if x.num_auto != p.num_auto]

    def _dt(v):
        try:
            return date.fromisoformat(str(v)[:10])
        except Exception:
            return None

    base = _dt(p.dt_auto)
    janela = [x for x in familia
              if x.municipio == p.municipio and base and _dt(x.dt_auto)
              and abs((_dt(x.dt_auto) - base).days) <= preverificacao.JANELA_MULTIPLAS_DIAS]

    # Perfil de dívida ativa federal — só pessoa jurídica, e só do AUTUADO.
    #
    # Duas tentativas, e a diferença entre elas vai escrita na evidência:
    # primeiro o CNPJ inteiro (aquele estabelecimento); se não houver, a raiz
    # (o grupo econômico). Um auto contra a filial não pode exibir a dívida da
    # matriz como se fosse dela.
    divida, escopo = None, None
    if p.cnpj:
        divida = db.query(DividaAtiva).filter(DividaAtiva.cnpj == p.cnpj).first()
        if divida:
            escopo = "estabelecimento"
        elif len(p.cnpj) >= 8:
            divida = (db.query(DividaAtiva)
                        .filter(DividaAtiva.raiz == p.cnpj[:8])
                        .order_by(DividaAtiva.valor_total.desc()).first())
            if divida:
                escopo = "grupo"

    # Notificações do MESMO processo administrativo. O número do processo do
    # auto vem formatado (02001.007833/2025-83) e o da notificação vem cru —
    # a comparação é feita só com os dígitos.
    notifs = []
    if p.processo:
        so = "".join(ch for ch in p.processo if ch.isdigit())
        if so:
            notifs = (db.query(Notificacao)
                        .filter(Notificacao.processo == so)
                        .order_by(Notificacao.dat_notificacao).limit(10).all())

    # Termos da MESMA fiscalização. Aqui o vínculo é o próprio número do auto,
    # declarado pelo IBAMA dentro do termo — o mais forte de todas as fontes.
    termos = (db.query(Termo)
                .filter(Termo.num_auto == p.num_auto)
                .order_by(Termo.tipo, Termo.data).limit(12).all())

    return preverificacao.pre_verificar(p, janela, familia,
                                        divida=divida, escopo_divida=escopo,
                                        notificacoes=notifs, termos=termos)


class CargaNotificacoes(BaseModel):
    notificacoes: list[dict]


@app.post("/api/notificacoes/carregar")
def carregar_notificacoes(req: CargaNotificacoes,
                          authorization: Optional[str] = Header(None),
                          db: Session = Depends(get_db)):
    """
    Carrega as notificações do IBAMA cujo processo consta da carteira.

    O arquivo público tem 439.187 notificações e 113 MB. Só 2.314 pertencem a
    processos que a carteira acompanha — o resto seria peso morto no banco.
    Como na dívida ativa, a filtragem acontece fora e aqui entra o recorte.

    O NÚMERO DA NOTIFICAÇÃO NÃO É ÚNICO NO ARQUIVO PÚBLICO
    -------------------------------------------------------
    Medido no recorte atual: 2.314 linhas para 2.313 números. O número 3U75N76D
    aparece duas vezes, no mesmo processo, com doze minutos de diferença e com
    campos COMPLEMENTARES — uma linha traz a forma de entrega e a situação, a
    outra traz a ordem de fiscalização e a unidade ordenadora. São duas
    publicações do mesmo ato, não dois atos. Por isso a carga consolida as
    repetições numa só linha em vez de rejeitá-las, e o dicionário `tocadas`
    guarda o que já foi criado nesta mesma remessa: a sessão não faz flush
    automático, de modo que uma consulta não enxergaria a linha recém-criada e
    o banco recusaria a chave repetida. Hoje é uma ocorrência; o arquivo é
    republicado a cada trimestre e nada garante que continue sendo.
    """
    _checar_auth(authorization)
    gravadas = 0
    tocadas: dict = {}
    for n in req.notificacoes:
        num = (n.get("num_notificacao") or "").strip()
        proc = "".join(ch for ch in (n.get("processo") or "") if ch.isdigit())
        if not num or not proc:
            continue
        linha = tocadas.get(num)
        if linha is None:
            linha = db.query(Notificacao).filter(Notificacao.num_notificacao == num).first()
        if not linha:
            linha = Notificacao(num_notificacao=num, processo=proc)
            db.add(linha)
        tocadas[num] = linha
        linha.processo = proc
        for campo in ("dat_notificacao", "prazo_apresentacao", "forma_entrega",
                      "des_ocorrencia", "des_atividade_notificado", "sit_atendida",
                      "sit_conclusao", "sit_auto_lavrado", "nom_municipio",
                      "sig_uf", "num_ordem_fiscalizacao", "unid_ordenadora"):
            if campo in n:
                setattr(linha, campo, n[campo])
        gravadas += 1
    db.commit()
    # `linhas_recebidas` e `notificacoes_distintas` podem divergir: ver a nota
    # sobre repetição do número no arquivo público, logo acima.
    return {"linhas_recebidas": gravadas,
            "notificacoes_distintas": len(tocadas),
            "total_na_base": db.query(Notificacao).count()}


class CargaTermos(BaseModel):
    termos: list[dict]


@app.post("/api/termos/carregar")
def carregar_termos(req: CargaTermos,
                    authorization: Optional[str] = Header(None),
                    db: Session = Depends(get_db)):
    """
    Carrega os termos do IBAMA cujo NUM_AUTO_INFRACAO consta da carteira.

    Os arquivos de origem somam mais de 320 MB (embargo sozinho tem 197 MB e
    116.057 linhas). Só 3.022 termos pertencem a autos que a carteira
    acompanha. Como na dívida ativa e na notificação, a filtragem acontece
    fora e aqui entra o recorte.

    Termos CANCELADOS não chegam nesta rota: são descartados na extração,
    porque um embargo cancelado exibido ao lado da pergunta induziria a erro
    exatamente na direção contrária à do resto do sistema.

    A chave é o número do termo. Vale a mesma cautela da notificação: se o
    arquivo público repetir um número numa remessa, `tocados` consolida em vez
    de deixar o banco recusar a chave — a sessão não faz flush automático e
    uma consulta não enxergaria a linha recém-criada.
    """
    _checar_auth(authorization)
    gravados = 0
    tocados: dict = {}
    for t in req.termos:
        num = (t.get("num_termo") or "").strip()
        auto = (t.get("num_auto") or "").strip()
        tipo = (t.get("tipo") or "").strip()
        if not num or not auto or not tipo:
            continue
        linha = tocados.get(num)
        if linha is None:
            linha = db.query(Termo).filter(Termo.num_termo == num).first()
        if not linha:
            linha = Termo(num_termo=num, tipo=tipo, num_auto=auto)
            db.add(linha)
        tocados[num] = linha
        linha.tipo, linha.num_auto = tipo, auto
        for campo in ("data", "municipio", "uf", "area", "tipo_area", "sit_desembargo",
                      "dat_desembargo", "des_desembargo", "descricao", "localizacao",
                      "forma_entrega", "justificativa", "valor",
                      "num_ordem_fiscalizacao", "unid_ordenadora"):
            if campo in t:
                setattr(linha, campo, t[campo])
        gravados += 1
    db.commit()
    return {"linhas_recebidas": gravados,
            "termos_distintos": len(tocados),
            "total_na_base": db.query(Termo).count()}


class CargaDividaAtiva(BaseModel):
    referencia_da_base: Optional[str] = None
    devedores: list[dict]


@app.post("/api/divida-ativa/carregar")
def carregar_divida_ativa(req: CargaDividaAtiva,
                          authorization: Optional[str] = Header(None),
                          db: Session = Depends(get_db)):
    """
    Carrega o perfil de dívida ativa federal dos autuados pessoa jurídica.

    POR QUE A CARGA É POR ROTA, E NÃO UMA MINERAÇÃO COMO A DO IBAMA
    ----------------------------------------------------------------
    O arquivo trimestral da PGFN tem 1,34 GB compactado e 9,04 GB abertos, em
    seis CSVs. Filtrar isso exige disco e memória que o plano deste serviço não
    tem — e a carteira só precisa das linhas dos CNPJs que ela acompanha, que
    somam menos de 1 MB depois de agregadas.

    Então a leitura pesada acontece fora, uma vez por trimestre, e aqui entra só
    o resultado. Idempotente: recarregar o mesmo trimestre sobrescreve.

    O QUE ESTA BASE NÃO RESPONDE
    -----------------------------
    Varri as 134 receitas que a PGFN publica: nenhuma identifica multa do IBAMA.
    Portanto isto NÃO liga a multa do auto a uma inscrição em dívida ativa. É o
    perfil de endividamento federal do autuado, e cada evidência gerada carrega
    essa ressalva por escrito.
    """
    _checar_auth(authorization)
    gravados = 0
    for d in req.devedores:
        cnpj = (d.get("cnpj") or "").strip()
        if not cnpj:
            continue
        cnpj = "".join(ch for ch in cnpj if ch.isdigit())
        if len(cnpj) != 14:
            continue
        linha = db.query(DividaAtiva).filter(DividaAtiva.cnpj == cnpj).first()
        if not linha:
            linha = DividaAtiva(cnpj=cnpj)
            db.add(linha)
        linha.raiz = cnpj[:8]
        for campo in ("nome", "uf", "inscricoes", "valor_total", "ajuizadas",
                      "corresponsavel", "solidario", "situacoes",
                      "receitas_principais", "inscricao_mais_antiga",
                      "inscricao_mais_recente"):
            if campo in d:
                setattr(linha, campo, d[campo])
        linha.referencia_da_base = req.referencia_da_base
        gravados += 1
    db.commit()
    return {"gravados": gravados,
            "total_na_base": db.query(DividaAtiva).count(),
            "referencia_da_base": req.referencia_da_base}


@app.get("/api/prospeccao/territorio")
def territorio(tipo_pessoa: str = "PF", topo: int = 50,
               authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """Onde os casos se concentram — a rota de aproximação para pessoa física."""
    _checar_auth(authorization)
    return enriquecimento.territorio(db, tipo_pessoa=tipo_pessoa, topo=min(topo, 200))


# ───────────────────────── Rotina diária de mineração ─────────────────────────

@app.post("/api/prospeccao/rotina-diaria")
def executar_rotina(
    ano: Optional[int] = None, baixar: bool = True, topo: int = 20,
    authorization: Optional[str] = Header(None), db: Session = Depends(get_db),
):
    """
    Baixa a base do dia, concilia com a carteira e devolve o boletim.
    Ponto único de entrada para o agendamento e para o botão do console.

    `topo` limita quantos casos vêm em CADA lista do boletim — os contadores
    seguem completos. Sem repassar este parâmetro, o console recebia 20 casos
    logo depois de minerar enquanto o contador continuava marcando 133, e a
    lista encolhia sem nenhuma explicação na tela.
    """
    _checar_auth(authorization)
    try:
        sinc = rotina.sincronizar(db, ano=ano, baixar=baixar, pasta=BASE_IBAMA)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(502, f"Falha na rotina de mineração: {e}")
    _cache_casos.clear()
    return {"sincronizacao": sinc, "boletim": rotina.boletim(db, topo=topo)}


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
    # Número do auto em análise. Faltava, e a falta tinha duas consequências:
    # o laudo saía sem dizer de qual auto ele trata, e o registro de acesso não
    # tinha como dizer sobre qual caso a pessoa trabalhou. Opcional para não
    # quebrar chamada antiga.
    numAuto: Optional[str] = None
    # Ids que vieram da pré-verificação, apurados sobre o registro público em
    # vez de respondidos por pessoa. O laudo declara essa separação: quem lê o
    # documento precisa saber o que foi conferido por alguém e o que é conta
    # sobre cadastro. Sem isso, o laudo afirmaria verificação humana que não
    # houve — que é a única forma de este produto enganar o próprio dono.
    apurados: Optional[list[str]] = None


@app.post("/api/auditoria")
def executar_auditoria(
    req: AuditoriaRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    _registrar(db, _checar_auth(authorization), "executou-auditoria",
               req.numAuto or (str(req.casoId) if req.casoId else None))
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
    _registrar(db, _checar_auth(authorization), "emitiu-laudo",
               req.numAuto or (str(req.casoId) if req.casoId else None))
    completo = catalogo.executar_auditoria(req.respostas, req.valorMulta)
    if req.casoId:
        caso = db.query(Caso).filter(Caso.id == req.casoId).first()
        if caso:
            caso.audit_result = completo
            db.commit()
    laudo = catalogo.laudo_tecnico(completo)
    if req.numAuto:
        laudo["num_auto"] = req.numAuto

    # A PROCEDÊNCIA DE CADA RESPOSTA VAI NO LAUDO.
    #
    # Item apurado sobre o registro público e item conferido por pessoa nas
    # peças do processo são coisas diferentes, e o documento tem de dizer qual
    # é qual. Sem esta declaração o laudo teria aparência de verificação
    # integral — o defeito que este sistema tem a obrigação de não cometer.
    apurados = [i for i in (req.apurados or []) if i in (req.respostas or {})]
    laudo["procedencia_das_respostas"] = {
        "apurados_sobre_o_registro_publico": sorted(apurados),
        "conferidos_por_pessoa": sorted(set(req.respostas or {}) - set(apurados)),
        "nota": (
            "Os itens apurados resultam de conta de chegada sobre o cadastro público "
            "do IBAMA (subtração de datas e cruzamento do acervo). O cadastro não é o "
            "auto nem o processo: campo ausente nele não prova peça ausente no "
            "processo. Os demais itens foram conferidos por quem assina a análise."
        ) if apurados else (
            "Todos os itens verificados foram conferidos por quem assina a análise."
        ),
        # AS BASES QUE PODEM TER INSTRUÍDO A CONFERÊNCIA.
        #
        # Nenhuma das quatro responde item nenhum — a resposta é sempre de
        # quem assina ou, nos poucos apurados, de conta aritmética. Mas quem
        # lê o laudo tem direito de saber que existiu material de consulta ao
        # lado das perguntas, e de onde ele veio. Sem esta lista, a evidência
        # que orientou a conferência ficaria invisível no documento.
        "bases_consultadas": [
            {"fonte": "IBAMA — Fiscalização/Auto de Infração",
             "papel": "cadastro administrativo do auto; origem dos itens apurados"},
            {"fonte": "PGFN — Dívida Ativa da União",
             "papel": "perfil fiscal do autuado; NÃO contém a multa deste auto, "
                      "pois a PGFN não identifica receitas do IBAMA entre as que publica"},
            {"fonte": "IBAMA — Fiscalização/Notificação",
             "papel": "notificação do MESMO processo administrativo; exibida como "
                      "evidência, nunca como resposta"},
            {"fonte": "IBAMA — Termos de embargo, apreensão e suspensão",
             "papel": "termos do MESMO número de auto; quando trazem área embargada, "
                      "o número é do TERMO e não do auto — preenche lacuna do cadastro "
                      "e não confirma a dosimetria"},
        ],
        "limite": (
            "Toda evidência exibida pelo sistema provém de registro administrativo "
            "público. Registro administrativo não é o processo: a ausência de um campo "
            "não prova a ausência da peça, e a presença de um dado não prova que ele "
            "foi o utilizado no ato impugnado."
        ),
    }

    # O valor da multa é fato, e acompanha o laudo. O valor projetado por
    # probabilidade de êxito, não — esse fica no anexo jurídico.
    if req.valorMulta:
        laudo["valor_da_multa_em_analise"] = req.valorMulta
    return laudo


@app.post("/api/anexo-juridico")
def emitir_anexo_juridico(req: AuditoriaRequest, authorization: Optional[str] = Header(None),
                          db: Session = Depends(get_db)):
    """
    Camada do ADVOGADO constituído pelo cliente — ou uso interno de priorização.
    Qualificação das constatações, teses, fundamentos, taxas e exposição financeira.
    """
    _registrar(db, _checar_auth(authorization), "emitiu-anexo-juridico",
               req.numAuto or (str(req.casoId) if req.casoId else None))
    completo = catalogo.executar_auditoria(req.respostas, req.valorMulta)
    return catalogo.anexo_juridico(completo)


# ═══════════════════════════════════════════════════════════════════════════
#  CÓPIA DE SEGURANÇA
# ═══════════════════════════════════════════════════════════════════════════
#
# NEM TUDO QUE ESTÁ NO BANCO PRECISA DE BACKUP — e confundir as duas coisas
# produziria um arquivo enorme que ninguém guarda.
#
# O banco mistura duas naturezas de dado:
#
#   REGENERÁVEL     a carteira de prospectos, os termos, as notificações e a
#                   dívida ativa. Tudo recorte de arquivo público. Se sumir,
#                   uma mineração e três cargas trazem de volta em minutos, e
#                   os arquivos de origem já estão na máquina.
#
#   INSUBSTITUÍVEL  o que foi produzido por PESSOAS: os casos abertos com sua
#                   auditoria, o status comercial de cada auto — selecionado,
#                   contatado, descartado, cliente —, as notas e o registro de
#                   acesso. Isso não existe em fonte nenhuma. Se sumir, sumiu.
#
# O backup leva o insubstituível inteiro e, do regenerável, apenas a CONTAGEM
# — que serve para conferir, depois de restaurar, se a remineração trouxe o
# mesmo volume. O arquivo fica pequeno, e arquivo pequeno é arquivo que
# alguém efetivamente guarda.
#
# Por que agora: o banco de produção é o plano gratuito do Render, que expira
# e é apagado com o que tem dentro. Enquanto a migração para o plano pago não
# acontece, este arquivo é a diferença entre perder uma data e perder o
# trabalho da equipe inteira.

@app.get("/api/backup")
def backup(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """
    Devolve tudo que NÃO se regenera a partir de fonte pública.
    """
    nome = _checar_auth(authorization)
    _registrar(db, nome, "gerou-backup", None)

    casos = [c.to_dict() for c in db.query(Caso).all()]

    # Só o que a equipe tocou. Prospecto em "novo" e sem nota é exatamente o
    # que a mineração recria — levá-lo seria inchar o arquivo com o que já
    # sabemos reproduzir.
    trabalho = [{"num_auto": p.num_auto, "status": p.status, "notas": p.notas,
                 "atualizado_em": p.atualizado_em.isoformat() if p.atualizado_em else None}
                for p in db.query(Prospecto)
                          .filter((Prospecto.status != "novo") | (Prospecto.notas.isnot(None)))
                          .all()]

    acessos = [a.to_dict() for a in db.query(Acesso).order_by(Acesso.em).all()]

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "versao_do_formato": 1,
        "insubstituivel": {"casos": casos, "trabalho_comercial": trabalho, "acessos": acessos},
        "regeneravel_apenas_contagem": {
            "prospectos": db.query(Prospecto).count(),
            "termos": db.query(Termo).count(),
            "notificacoes": db.query(Notificacao).count(),
            "divida_ativa": db.query(DividaAtiva).count(),
        },
        "como_restaurar": (
            "1) POST /api/prospeccao/atualizar para reminerar a carteira do arquivo do IBAMA. "
            "2) ferramentas/carregar-termos.ps1, carregar-notificacoes.ps1 e "
            "carregar-divida-ativa.ps1 para recarregar os recortes. "
            "3) POST /api/restaurar com este arquivo inteiro no corpo. "
            "Ao final, confira se as contagens batem com regeneravel_apenas_contagem."
        ),
    }


class Restauracao(BaseModel):
    insubstituivel: dict
    versao_do_formato: Optional[int] = None
    gerado_em: Optional[str] = None


@app.post("/api/restaurar")
def restaurar(req: Restauracao, authorization: Optional[str] = Header(None),
              db: Session = Depends(get_db)):
    """
    Repõe o que o backup levou. NUNCA APAGA NADA.

    Idempotente, e só acrescenta ou atualiza. É deliberado: restaurar um
    backup velho por engano num banco vivo não pode destruir o que foi feito
    depois dele.

    E "não destruir" aqui é regra de código, não intenção. O primeiro teste
    desta rota mostrou que a versão anterior sobrescrevia com a nota antiga
    uma nota escrita DEPOIS do backup — perda silenciosa, exatamente o que a
    rota existe para evitar. A regra que resolve:

      · registro que ainda NÃO tem trabalho (status "novo", sem nota) é sempre
        reposto — é o caso do banco recém-reminerado depois do desastre;
      · registro que JÁ tem trabalho e foi tocado depois da data do backup é
        PRESERVADO, e volta em `preservados_por_serem_mais_novos`.

    O status comercial só é reposto em prospecto que EXISTE. Se a carteira
    ainda não foi reminerada, esses itens voltam em `nao_encontrados` e a
    chamada pode ser repetida depois da mineração, sem efeito colateral.
    """
    nome = _checar_auth(authorization)
    _registrar(db, nome, "restaurou-backup", req.gerado_em or None)

    def _quando(v):
        try:
            return datetime.fromisoformat(v) if v else None
        except (ValueError, TypeError):
            return None

    ins = req.insubstituivel or {}
    preservados = []
    casos_novos = casos_atualizados = 0
    for c in ins.get("casos") or []:
        cid = (c.get("id") or "").strip()
        if not cid:
            continue
        linha = db.query(Caso).filter(Caso.id == cid).first()
        if linha:
            do_backup, no_banco = _quando(c.get("updatedAt")), linha.updated_at
            if do_backup and no_banco and no_banco > do_backup:
                preservados.append(f"caso {cid}")
                continue
            casos_atualizados += 1
        else:
            linha = Caso(id=cid)
            db.add(linha)
            casos_novos += 1
        linha.form_data = c.get("formData") or {}
        linha.audit_result = c.get("auditResult")
        linha.geo_verificacoes = c.get("geoVerificacoes") or []

    repostos = 0
    nao_encontrados = []
    for t in ins.get("trabalho_comercial") or []:
        na = (t.get("num_auto") or "").strip()
        if not na:
            continue
        p = db.query(Prospecto).filter(Prospecto.num_auto == na).first()
        if not p:
            nao_encontrados.append(na)
            continue
        # Só preserva o que JÁ tem trabalho feito. Prospecto recém-reminerado
        # está em "novo" e sem nota: esse é o alvo da restauração, ainda que
        # sua data de atualização seja mais recente que a do backup.
        tem_trabalho = (p.status or "novo") != "novo" or p.notas
        if tem_trabalho:
            do_backup, no_banco = _quando(t.get("atualizado_em")), p.atualizado_em
            if do_backup and no_banco and no_banco > do_backup:
                preservados.append(na)
                continue
        if t.get("status"):
            p.status = t["status"]
        if t.get("notas") is not None:
            p.notas = t["notas"]
        repostos += 1

    # O registro de acesso é histórico: entra sem sobrescrever o que já existe.
    ja = {(a.quem, a.acao, a.alvo, a.em.isoformat() if a.em else None)
          for a in db.query(Acesso).all()}
    acessos_repostos = 0
    for a in ins.get("acessos") or []:
        if (a.get("quem"), a.get("acao"), a.get("alvo"), a.get("em")) in ja:
            continue
        try:
            em = datetime.fromisoformat(a["em"]) if a.get("em") else None
        except (ValueError, TypeError):
            em = None
        db.add(Acesso(quem=a.get("quem") or "?", acao=a.get("acao") or "?",
                      alvo=a.get("alvo"), em=em))
        acessos_repostos += 1

    db.commit()
    return {
        "casos_criados": casos_novos,
        "casos_atualizados": casos_atualizados,
        "trabalho_comercial_reposto": repostos,
        "acessos_repostos": acessos_repostos,
        "nao_encontrados_na_carteira": nao_encontrados[:50],
        "total_nao_encontrados": len(nao_encontrados),
        "preservados_por_serem_mais_novos": preservados[:50],
        "total_preservados": len(preservados),
        "aviso": ("Itens em nao_encontrados são autos que ainda não estão na carteira. "
                  "Remine e repita esta chamada — ela é idempotente."
                  if nao_encontrados else "Restauração completa."),
    }


@app.get("/api/acessos")
def listar_acessos(alvo: Optional[str] = None, quem: Optional[str] = None,
                   limite: int = 200, authorization: Optional[str] = Header(None),
                   db: Session = Depends(get_db)):
    """
    Lê o registro de acesso: quem consultou qual caso, e quando.

    Filtra por `alvo` (número do auto) para responder à pergunta que motivou
    esta tabela — "quem acessou este processo" — e por `quem` para a pergunta
    inversa. Sem filtro, devolve os últimos acessos.

    A própria leitura é registrada. Auditoria que não se audita tem um ponto
    cego exatamente onde mais importa.
    """
    nome = _checar_auth(authorization)
    _registrar(db, nome, "leu-registro-de-acesso", alvo or quem or None)
    q = db.query(Acesso)
    if alvo:
        q = q.filter(Acesso.alvo == alvo)
    if quem:
        q = q.filter(Acesso.quem == quem)
    linhas = q.order_by(Acesso.em.desc()).limit(max(1, min(limite, 1000))).all()
    return {"total_no_filtro": q.count(),
            "acessos": [a.to_dict() for a in linhas]}


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
