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


def executar_auditoria(respostas: dict[str, str]) -> dict:
    """
    respostas: {"1.1": "ok" | "fail" | "na", ...}

    Devolve o diagnóstico completo. Duas leituras de score, ambas explícitas:

      · score            — falhas sobre o que foi de fato avaliado (exclui N/A).
                           É a leitura honesta quando o processo ainda não foi
                           todo verificado.
      · score_absoluto   — falhas sobre o total do catálogo (448 pontos).
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
        "metodologia": cat["regra_de_peso"],
    }
