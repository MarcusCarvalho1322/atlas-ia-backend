"""
Motor de prospecção — identificação, seleção e mineração de casos relevantes.

Ingere a base pública de autos de infração do IBAMA e ordena os casos por
relevância, usando SOMENTE sinais aritméticos verificáveis no próprio dado.

Fonte: IBAMA — Dados Abertos, dataset "Fiscalização — Auto de Infração"
  https://dadosabertos.ibama.gov.br/dataset/fiscalizacao-auto-de-infracao
  Atualização diária. Cobertura nacional desde 1980. 84 colunas.

PRINCÍPIO — o mesmo das duas camadas do laudo: aqui só se produz CONSTATAÇÃO
(intervalos de datas, valores, presença de coordenada). A qualificação desses
sinais como nulidade, e a estimativa de êxito, ficam fora deste módulo: são
leitura de advogado e vivem em catalogo.anexo_juridico().

DADOS PESSOAIS — nome e CPF/CNPJ são publicados pelo próprio IBAMA, mas o uso
para prospecção comercial é finalidade distinta da publicação original. Por
isso o documento sai mascarado por padrão (mesma prática do SafraCheck, que
grava "***" + 4 últimos dígitos nos registros de validação). Use
`revelar_documento=True` apenas onde houver base legal registrada para tanto.
"""
from __future__ import annotations
import csv, math, sys
from dataclasses import dataclass, asdict, field
from datetime import date, datetime
from pathlib import Path

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

FONTE = "IBAMA — Dados Abertos · Fiscalização/Auto de Infração"
FONTE_URL = "https://dadosabertos.ibama.gov.br/dataset/fiscalizacao-auto-de-infracao"

# Situações que retiram o auto do universo de prospecção.
SITUACOES_DESCARTE = {"excluído", "excluido", "cancelado"}

PRAZO_DEFESA_DIAS = 20        # Dec. 6.514/08 — prazo para defesa a contar da ciência
JANELA_PRESCRICAO_ANOS = 3    # art. 21 Dec. 6.514/08 — pretensão punitiva


def _data(s: str | None) -> date | None:
    s = (s or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _num(s: str | None) -> float | None:
    s = (s or "").strip().replace(".", "").replace(",", ".")
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


def _coord(s: str | None) -> float | None:
    s = (s or "").strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _cnpj_se_pj(tipo: str | None, doc: str | None) -> str | None:
    """Devolve o CNPJ apenas quando o autuado é pessoa jurídica."""
    if (tipo or "").strip().upper() != "PJ":
        return None
    d = "".join(c for c in (doc or "") if c.isdigit())
    return d if len(d) == 14 else None


def _mascarar(doc: str | None) -> str | None:
    d = "".join(ch for ch in (doc or "") if ch.isdigit())
    return ("***" + d[-4:]) if len(d) >= 4 else None


@dataclass
class Sinal:
    """Constatação aritmética sobre o registro. Sem qualificação jurídica."""
    codigo: str
    constatacao: str
    peso: int


# As colunas do registro público que o protocolo de 60 itens realmente usa.
#
# A base do IBAMA tem 84 colunas. Guardar as 84 encheria o banco de campos de
# controle interno do órgão que não respondem a pergunta nenhuma; guardar 15,
# como se fazia, deixava de fora o enquadramento legal, a dosimetria, a forma
# de entrega da notificação, a área autuada e os marcos de prescrição.
#
# Cada campo desta lista está amarrado a pelo menos um item do protocolo — a
# correspondência vive em preverificacao.py, onde é aplicada.
CAMPOS_DO_REGISTRO = (
    # conduta e enquadramento — itens 1.2 e 1.3
    "DES_AUTO_INFRACAO", "DES_INFRACAO", "COD_INFRACAO",
    "DS_ENQUADRAMENTO_ADMINISTRATIVO", "DS_ENQUADRAMENTO_NAO_ADMINISTRATIVO",
    "DS_ENQUADRAMENTO_COMPLEMENTAR",
    # área e cálculo — itens 1.4, 4.9 e 5.2
    "QT_AREA", "INFRACAO_AREA", "CLASSIFICACAO_AREA", "DS_FATOR_AJUSTE",
    "WKT_GE_AREA_AUTUADA", "TP_ORIGEM_GE_AREA_AUTUADA", "DS_ERRO_GE_AREA_AUTUADA",
    # dosimetria — item 5.1
    "GRAVIDADE_INFRACAO", "CD_NIVEL_GRAVIDADE", "MOTIVACAO_CONDUTA",
    "EFEITO_MEIO_AMBIENTE", "EFEITO_SAUDE_PUBLICA", "FUNDAMENTACAO_MULTA", "TIPO_MULTA",
    # notificação — itens 3.1 a 3.4
    "FORMA_ENTREGA",
    # diligência e provas — itens 1.12 e 4.2
    "ORDEM_FISCALIZACAO", "UNID_ORDENADORA", "DS_REFERENCIA_ACAO_FISCALIZATORIA",
    "TIPO_ACAO", "OPERACAO", "DES_LOCAL_INFRACAO", "DS_WKT",
    # competência — itens 2.3 e 2.4
    "UNIDADE_CONSERVACAO",
    # prazos — módulo 6
    "DT_INICIO_ATO_INEQUIVOCO", "DT_FIM_ATO_INEQUIVOCO",
    # instrução e recurso — itens 8.3, 9.1 e 9.2
    "PASSIVEL_RECUPERACAO", "SOLICITACAO_RECURSO",
    "CD_TERMOS_APREENSAO", "CD_TERMOS_EMBARGOS",
)


def _recorte_do_registro(row: dict) -> dict:
    """Só chaves com valor. O que não veio da fonte não existe, em vez de
    existir vazio — assim `campo ausente` significa mesmo ausente."""
    out = {}
    for c in CAMPOS_DO_REGISTRO:
        v = (row.get(c) or "").strip()
        if v:
            out[c] = v
    return out


@dataclass
class Caso:
    num_auto: str
    processo: str | None
    valor: float | None
    uf: str | None
    municipio: str | None
    bioma: str | None
    tipo_infracao: str | None
    tipo_pessoa: str | None
    documento_mascarado: str | None
    cnpj: str | None
    nome: str | None
    dt_fato: date | None
    dt_auto: date | None
    dt_ciencia: date | None
    lat: float | None
    lon: float | None
    # Recorte cru do registro público — ver CAMPOS_DO_REGISTRO.
    registro: dict = field(default_factory=dict)
    sinais: list[Sinal] = field(default_factory=list)
    prioridade: float = 0.0
    dias_para_defesa: int | None = None
    # Usado só para desempatar linhas repetidas do mesmo auto; não vai para a API.
    _alterado_em: str = ""

    def to_dict(self, revelar_documento=False):
        d = asdict(self)
        d.pop("_alterado_em", None)
        d["dt_fato"] = self.dt_fato.isoformat() if self.dt_fato else None
        d["dt_auto"] = self.dt_auto.isoformat() if self.dt_auto else None
        d["dt_ciencia"] = self.dt_ciencia.isoformat() if self.dt_ciencia else None
        if not revelar_documento:
            d.pop("nome", None)
        return d


def _avaliar(c: Caso, hoje: date) -> None:
    """Aplica os sinais objetivos. Cada um é aritmética sobre o próprio dado."""
    s = c.sinais

    if c.dt_fato and c.dt_auto:
        anos = (c.dt_auto - c.dt_fato).days / 365.25
        if anos > JANELA_PRESCRICAO_ANOS:
            s.append(Sinal("DECURSO_FATO_AUTO",
                           f"Transcorreram {anos:.1f} anos entre a data do fato e a lavratura do auto.", 10))
        if (c.dt_auto - c.dt_fato).days < 0:
            s.append(Sinal("INVERSAO_TEMPORAL",
                           f"O auto foi lavrado {abs((c.dt_auto - c.dt_fato).days)} dia(s) ANTES da data do fato registrada.", 10))

    if c.dt_ciencia:
        venc = c.dt_ciencia.toordinal() + PRAZO_DEFESA_DIAS
        c.dias_para_defesa = venc - hoje.toordinal()
        if 0 <= c.dias_para_defesa <= 20:
            s.append(Sinal("PRAZO_DEFESA_ABERTO",
                           f"Prazo de defesa administrativa em curso: restam {c.dias_para_defesa} dia(s) desde a ciência.", 10))
    elif c.dt_auto:
        s.append(Sinal("SEM_DATA_CIENCIA",
                       "O registro público não informa data de ciência da autuação.", 4))

    if c.lat is None or c.lon is None:
        s.append(Sinal("SEM_COORDENADA",
                       "O registro público não traz coordenadas geográficas da infração.", 7))

    if c.valor is None:
        s.append(Sinal("SEM_VALOR", "O registro público não informa o valor da multa.", 4))


def _prioridade(c: Caso) -> float:
    """
    Ordena por relevância comercial: porte financeiro combinado com a densidade
    de sinais e com a urgência do prazo. Escala logarítmica no valor para que um
    caso de R$ 50 milhões não afogue toda a lista.
    """
    porte = math.log10(c.valor) if c.valor and c.valor > 1 else 0.0
    densidade = sum(x.peso for x in c.sinais) / 10.0
    urgencia = 0.0
    if c.dias_para_defesa is not None and 0 <= c.dias_para_defesa <= 20:
        urgencia = 3.0 * (1 - c.dias_para_defesa / 20)
    return round(porte * 1.5 + densidade + urgencia, 3)


def ingerir(caminho: str | Path, hoje: date | None = None, limite: int | None = None) -> list[Caso]:
    """Lê um CSV anual do dataset e devolve os casos vivos, já avaliados."""
    hoje = hoje or date.today()
    por_auto: dict[str, Caso] = {}
    with open(caminho, encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            if (row.get("SIT_CANCELADO") or "").strip().upper() not in ("", "N", "NAO", "NÃO"):
                continue
            if (row.get("DS_SIT_AUTO_AIE") or "").strip().lower() in SITUACOES_DESCARTE:
                continue
            if (row.get("DES_STATUS_FORMULARIO") or "").strip().lower() in SITUACOES_DESCARTE:
                continue

            c = Caso(
                num_auto=(row.get("NUM_AUTO_INFRACAO") or "").strip(),
                processo=(row.get("NU_PROCESSO_FORMATADO") or "").strip() or None,
                valor=_num(row.get("VAL_AUTO_INFRACAO")),
                uf=(row.get("UF") or "").strip() or None,
                municipio=(row.get("MUNICIPIO") or "").strip() or None,
                bioma=(row.get("DS_BIOMAS_ATINGIDOS") or "").strip() or None,
                tipo_infracao=(row.get("TIPO_INFRACAO") or "").strip() or None,
                tipo_pessoa=(row.get("TP_PESSOA_INFRATOR") or "").strip() or None,
                documento_mascarado=_mascarar(row.get("CPF_CNPJ_INFRATOR")),
                # Só para PJ. CPF de pessoa física não é guardado por extenso.
                cnpj=_cnpj_se_pj(row.get("TP_PESSOA_INFRATOR"), row.get("CPF_CNPJ_INFRATOR")),
                nome=(row.get("NOME_INFRATOR") or "").strip() or None,
                dt_fato=_data(row.get("DT_FATO_INFRACIONAL")),
                dt_auto=_data(row.get("DAT_HORA_AUTO_INFRACAO")),
                dt_ciencia=_data(row.get("DAT_CIENCIA_AUTUACAO")),
                lat=_coord(row.get("NUM_LATITUDE_AUTO")),
                lon=_coord(row.get("NUM_LONGITUDE_AUTO")),
                registro=_recorte_do_registro(row),
                _alterado_em=((row.get("DT_ULT_ALTERACAO") or row.get("DT_LANCAMENTO") or "").strip()),
            )
            if not c.num_auto:
                continue
            _avaliar(c, hoje)
            c.prioridade = _prioridade(c)

            # O dataset traz mais de uma linha para o mesmo auto — versões
            # sucessivas do registro, e às vezes a linha cancelada ao lado da
            # viva. Um auto é um prospecto: fica a versão mais recente.
            anterior = por_auto.get(c.num_auto)
            if anterior is None or c._alterado_em > anterior._alterado_em:
                por_auto[c.num_auto] = c
            if limite and len(por_auto) >= limite:
                break

    casos = sorted(por_auto.values(), key=lambda x: -x.prioridade)
    return casos


def ranquear(casos: list[Caso], uf: str | None = None, valor_minimo: float | None = None,
             sinal: str | None = None, topo: int = 50) -> list[Caso]:
    sel = casos
    if uf:
        sel = [c for c in sel if c.uf == uf.upper()]
    if valor_minimo:
        sel = [c for c in sel if (c.valor or 0) >= valor_minimo]
    if sinal:
        sel = [c for c in sel if any(s.codigo == sinal for s in c.sinais)]
    return sel[:topo]


def resumo(casos: list[Caso]) -> dict:
    from collections import Counter
    sinais = Counter(s.codigo for c in casos for s in c.sinais)
    ufs = Counter(c.uf for c in casos if c.uf)
    total = sum(c.valor or 0 for c in casos)
    return {
        "fonte": FONTE, "fonte_url": FONTE_URL,
        "casos_vivos": len(casos),
        "valor_total": round(total, 2),
        "valor_medio": round(total / len(casos), 2) if casos else 0,
        "por_sinal": dict(sinais.most_common()),
        "por_uf": dict(ufs.most_common(10)),
        "com_coordenada": sum(1 for c in casos if c.lat and c.lon),
        "prazo_defesa_aberto": sum(1 for c in casos if c.dias_para_defesa is not None and 0 <= c.dias_para_defesa <= 20),
    }


# ─────────────────────────────────────────────────────────────────────────
# Atualização da base. O IBAMA republica o pacote diariamente; o arquivo é
# um zip com um CSV por ano (~116 MB no total). Só os anos pedidos são
# extraídos, para não carregar 46 anos de histórico sem necessidade.
# ─────────────────────────────────────────────────────────────────────────
URL_PACOTE = ("https://stibamadadosabertosprd.blob.core.windows.net/dados-abertos/"
              "dados/SIFISC/auto_infracao/auto_infracao/auto_infracao_csv.zip")


def baixar_base(destino: str | Path, anos: list[int] | None = None, timeout: float = 600.0) -> list[Path]:
    """
    Baixa o pacote do IBAMA e extrai os CSVs dos anos pedidos.

    O download é gravado em arquivo temporário no disco, não em memória: o
    pacote passa de 115 MB e, somado à extração, estouraria a folga de uma
    instância pequena. Assim o serviço roda confortável em 512 MB.
    """
    import zipfile, tempfile, os, httpx
    destino = Path(destino); destino.mkdir(parents=True, exist_ok=True)
    anos = anos or [date.today().year]

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    try:
        with httpx.stream("GET", URL_PACOTE, timeout=timeout, follow_redirects=True) as r:
            r.raise_for_status()
            for chunk in r.iter_bytes(1 << 20):
                tmp.write(chunk)
        tmp.close()

        extraidos = []
        with zipfile.ZipFile(tmp.name) as z:
            nomes = set(z.namelist())
            for ano in anos:
                nome = f"auto_infracao_{ano}.csv"
                if nome not in nomes:
                    continue
                alvo = destino / nome
                # Extração em blocos, pelo mesmo motivo do download.
                with z.open(nome) as origem, open(alvo, "wb") as saida:
                    while bloco := origem.read(1 << 20):
                        saida.write(bloco)
                extraidos.append(alvo)
        return extraidos
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
