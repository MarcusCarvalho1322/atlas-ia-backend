"""
Catálogo de auditoria do ATLAS-IA — fonte única de verdade.

Antes desta integração, as listas de verificação viviam duplicadas em dois
arquivos do front-end (App.jsx tinha NAMES/TESES/WEIGHTS/TAXAS/RISCOS e
IntakeTab.jsx tinha CHECKS/CHECK_INVERT), obrigadas a ficar sincronizadas
pela posição no array — se alguém inserisse um item no meio de uma lista e
não na outra, o sistema passaria a exibir a tese errada para a resposta
errada, silenciosamente.

Agora o catálogo existe uma única vez, aqui, e o front-end o consome pela
API. Conteúdo consolidado de duas fontes reais do próprio acervo:
  · ATLAS-IA (app React) — 20 nulidades com teses e taxas
  · ATLAS FORENSE v2.1 — 55 itens de verificação em 8 módulos + 20 nulidades
    (o catálogo hoje tem 60 itens em 9 módulos, com os 5 acrescidos na v1.1)

Onde as duas fontes divergem sobre a taxa de êxito de uma tese, o conflito
fica REGISTRADO no catálogo (campos `taxa_divergente` e `nota_divergencia`),
nunca resolvido por média ou escolha arbitrária: essa decisão é do advogado
responsável, não do sistema.
"""
import json
from pathlib import Path
from functools import lru_cache

_ARQ = Path(__file__).parent / "catalogo.json"

# Faixas do score de potencial defensivo (mesmos cortes do ATLAS-IA original)
FAIXA_ALTA, FAIXA_MEDIA = 60, 30


@lru_cache(maxsize=1)
def carregar() -> dict:
    return json.loads(_ARQ.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _indices():
    cat = carregar()
    return (
        {i["id"]: i for i in cat["itens"]},
        {n["id"]: n for n in cat["nulidades"]},
        {m["id"]: m for m in cat["modulos"]},
    )


def _valor_em_risco(multa, teses: list[dict]) -> dict | None:
    """
    Traduz a auditoria em dinheiro — que é a linguagem em que o cliente decide.

    REGRA DELIBERADA: usa a MAIOR taxa entre as teses acionáveis, nunca a soma
    nem o produto. Somar probabilidades de teses diferentes produziria número
    inflado e sem significado — é a mesma regra que o ARGUS TarifaCheck já
    adota para alíquotas ("não somar automaticamente").

    Não é previsão de resultado: é a exposição financeira associada à tese de
    maior êxito registrado no acervo, para dimensionar a causa.
    """
    try:
        valor = float(str(multa).replace(",", ".")) if multa not in (None, "") else 0.0
    except (TypeError, ValueError):
        return None
    if valor <= 0 or not teses:
        return None

    melhor = max(teses, key=lambda t: t["taxa"])
    return {
        "valor_multa": round(valor, 2),
        "tese_de_maior_exito": {"id": melhor["id"], "nome": melhor["nome"], "taxa": melhor["taxa"]},
        "valor_em_risco_reversivel": round(valor * melhor["taxa"] / 100, 2),
        "criterio": ("Valor da multa multiplicado pela taxa de êxito registrada da tese mais forte. "
                     "As taxas NÃO são somadas entre teses — a soma de probabilidades de teses "
                     "distintas não tem significado estatístico."),
        "aviso": ("Estimativa indicativa para dimensionar a causa. Não é previsão de resultado nem "
                  "promessa de êxito, e não substitui a análise do advogado responsável."),
    }


def executar_auditoria(respostas: dict[str, str], valor_multa=None) -> dict:
    """
    respostas: {"1.1": "ok" | "fail" | "na", ...}
    valor_multa: valor original da multa, para calcular a exposição financeira.

    Devolve o diagnóstico completo. Duas leituras de score, ambas explícitas:

      · score            — falhas sobre o que foi de fato avaliado (exclui N/A).
                           É a leitura honesta quando o processo ainda não foi
                           todo verificado.
      · score_absoluto   — falhas sobre o total do catálogo (486 pontos).
                           Só é comparável entre casos totalmente preenchidos.

    O sistema não emite juízo jurídico: aponta falhas e as teses associadas,
    com a taxa de êxito registrada e sua origem. A leitura é do advogado.
    """
    itens, nuls, mods = _indices()
    cat = carregar()

    falhas, conformes, na = [], [], []
    por_modulo = {m["id"]: {"titulo": m["titulo"], "falhas": 0, "conformes": 0,
                            "na": 0, "peso_falha": 0, "peso_avaliado": 0}
                  for m in cat["modulos"]}

    for item_id, resp in (respostas or {}).items():
        it = itens.get(item_id)
        if not it:
            continue
        bloco = por_modulo[it["modulo"]]
        if resp == "fail":
            falhas.append(it)
            bloco["falhas"] += 1
            bloco["peso_falha"] += it["peso"]
            bloco["peso_avaliado"] += it["peso"]
        elif resp == "ok":
            conformes.append(it)
            bloco["conformes"] += 1
            bloco["peso_avaliado"] += it["peso"]
        elif resp == "na":
            na.append(it)
            bloco["na"] += 1

    peso_falha = sum(i["peso"] for i in falhas)
    peso_avaliado = peso_falha + sum(i["peso"] for i in conformes)
    total = cat["pontuacao_maxima"]

    score = round(peso_falha / peso_avaliado * 100) if peso_avaliado else 0
    score_absoluto = round(peso_falha / total * 100)

    # Teses acionáveis, sem repetição, ordenadas pela taxa de êxito registrada.
    acionaveis = {}
    for it in falhas:
        for tid in it["teses"]:
            n = nuls[tid]
            alvo = acionaveis.setdefault(tid, {**n, "itens_que_sustentam": []})
            alvo["itens_que_sustentam"].append({"id": it["id"], "titulo": it["titulo"]})
    teses = sorted(acionaveis.values(), key=lambda n: n["taxa"], reverse=True)

    for b in por_modulo.values():
        b["score"] = round(b["peso_falha"] / b["peso_avaliado"] * 100) if b["peso_avaliado"] else None

    if score >= FAIXA_ALTA:
        nivel = "ALTO POTENCIAL — múltiplas nulidades sustentadas"
    elif score >= FAIXA_MEDIA:
        nivel = "MÉDIO POTENCIAL — nulidades relevantes identificadas"
    else:
        nivel = "BAIXO POTENCIAL — concentrar em dosimetria e redução do valor"

    return {
        "score": score,
        "score_absoluto": score_absoluto,
        "nivel": nivel,
        "peso_falha": peso_falha,
        "peso_avaliado": peso_avaliado,
        "pontuacao_maxima": total,
        "itens_respondidos": len(falhas) + len(conformes) + len(na),
        "itens_no_catalogo": len(itens),
        "resumo": {
            "falhas": len(falhas), "conformes": len(conformes), "na": len(na),
            "criticas": sum(1 for i in falhas if i["risco"] == "CRITICO"),
            "altas": sum(1 for i in falhas if i["risco"] == "ALTO"),
            "medias": sum(1 for i in falhas if i["risco"] == "MEDIO"),
        },
        "por_modulo": por_modulo,
        "falhas": [
            {"id": i["id"], "modulo": i["modulo"], "titulo": i["titulo"],
             "risco": i["risco"], "peso": i["peso"], "nota_risco": i["nota_risco"],
             "acao": i["acao"], "teses": i["teses"]}
            for i in sorted(falhas, key=lambda x: (-x["peso"], x["id"]))
        ],
        "teses_acionaveis": teses,
        "exposicao_financeira": _valor_em_risco(valor_multa, teses),
        "metodologia": cat["regra_de_peso"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# AS DUAS CAMADAS DE SAÍDA
#
# A auditoria completa acima é uso INTERNO. Ela mistura constatação técnica
# com qualificação jurídica, e a segunda é atividade privativa de advogado
# (Lei 8.906/94, art. 1º). As duas funções abaixo projetam esse resultado nas
# camadas que efetivamente saem do sistema:
#
#   laudo_tecnico()   → consumidor final. Só fato verificável. Sem tese, sem
#                       taxa de êxito, sem jurisprudência, sem valor projetado
#                       por probabilidade.
#   anexo_juridico()  → advogado contratado pelo cliente, ou uso interno de
#                       priorização comercial.
#
# Regra de segurança: a separação vale no SERVIDOR. O aplicativo do consumidor
# chama o endpoint do laudo e a camada jurídica nunca trafega até ele.
# ═══════════════════════════════════════════════════════════════════════════

AVISO_LAUDO = (
    "Este documento reúne CONSTATAÇÕES TÉCNICAS sobre a instrução do processo "
    "administrativo, apuradas a partir das peças analisadas e de bases oficiais "
    "públicas. Não constitui parecer jurídico, não qualifica as constatações como "
    "nulidades e não avalia chances de êxito — essa leitura é atividade privativa "
    "de advogado (Lei 8.906/94, art. 1º) e cabe ao profissional que o interessado "
    "vier a constituir."
)


def laudo_tecnico(auditoria: dict) -> dict:
    """Camada do consumidor final: o que foi verificado e o que se constatou."""
    itens, _, mods = _indices()

    achados = []
    for f in auditoria.get("falhas", []):
        it = itens.get(f["id"])
        if not it:
            continue
        t = it.get("tecnico", {})
        achados.append({
            "id": it["id"],
            "modulo": mods[it["modulo"]].get("titulo_tecnico") or mods[it["modulo"]]["titulo"],
            "constatacao": t.get("titulo", it["titulo"]),
            "verificacao_realizada": t.get("verificacao", it["pergunta"]),
            "gravidade_tecnica": t.get("gravidade"),
            "providencia_tecnica": t.get("providencia_tecnica"),
        })

    ordem = {"DETERMINANTE": 0, "RELEVANTE": 1, "ACESSORIO": 2}
    achados.sort(key=lambda a: (ordem.get(a["gravidade_tecnica"], 9), a["id"]))
    r = auditoria.get("resumo", {})

    return {
        "tipo": "laudo_tecnico",
        "itens_verificados": r.get("falhas", 0) + r.get("conformes", 0),
        "itens_no_protocolo": auditoria.get("itens_no_catalogo"),
        "conformes": r.get("conformes", 0),
        "nao_conformes": r.get("falhas", 0),
        "nao_aplicaveis": r.get("na", 0),
        "distribuicao_por_gravidade": {
            "determinante": sum(1 for a in achados if a["gravidade_tecnica"] == "DETERMINANTE"),
            "relevante": sum(1 for a in achados if a["gravidade_tecnica"] == "RELEVANTE"),
            "acessorio": sum(1 for a in achados if a["gravidade_tecnica"] == "ACESSORIO"),
        },
        "achados": achados,
        "indice_de_inconformidade": auditoria.get("score"),
        "metodologia": (
            "Protocolo de verificação documental e metrológica aplicado sobre as peças do "
            "processo. Cada item recebe peso uniforme por gravidade técnica "
            "(determinante 10, relevante 7, acessório 4). O índice de inconformidade é a "
            "razão entre o peso das não conformidades e o peso do que foi efetivamente "
            "verificado — não é probabilidade de resultado."
        ),
        "aviso": AVISO_LAUDO,
    }


def anexo_juridico(auditoria: dict) -> dict:
    """Camada do advogado: qualificação, teses, fundamentos e taxas."""
    itens, _, _ = _indices()

    encaminhamentos = []
    for f in auditoria.get("falhas", []):
        it = itens.get(f["id"])
        if not it:
            continue
        j = it.get("juridico", {})
        if j.get("qualificacao") or j.get("encaminhamento_juridico"):
            encaminhamentos.append({
                "id": it["id"],
                "constatacao": it["titulo"],
                "qualificacao": j.get("qualificacao"),
                "encaminhamento": j.get("encaminhamento_juridico"),
                "teses": j.get("teses", []),
            })

    return {
        "tipo": "anexo_juridico",
        "destinatario": "Advogado constituído pelo interessado — ou uso interno de priorização.",
        "teses_acionaveis": auditoria.get("teses_acionaveis", []),
        "encaminhamentos": encaminhamentos,
        "exposicao_financeira": auditoria.get("exposicao_financeira"),
        "aviso": (
            "As taxas de êxito são indicativas, extraídas do acervo ATLAS FORENSE e do "
            "ATLAS-IA, e carecem de reconferência contra as fontes primárias (TCU, IBAMA, "
            "PGFN). Não constituem previsão de resultado. Onde as fontes divergem, ambos os "
            "valores estão registrados. Material de apoio: não substitui a análise do "
            "advogado responsável."
        ),
    }
