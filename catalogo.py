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


# ═══════════════════════════════════════════════════════════════════════════
#  A PROCEDÊNCIA DAS TAXAS DE ÊXITO — e o que foi possível verificar
# ═══════════════════════════════════════════════════════════════════════════
#
# As 28 teses do catálogo trazem uma "taxa de êxito" (72%, 95%, 55%...). Esses
# percentuais são a informação de maior risco do produto inteiro, e o motivo é
# simples: são a única coisa que o sistema afirma sem conseguir mostrar de onde
# tirou.
#
# O próprio catálogo declara a origem — os dois sistemas anteriores. Nenhum
# deles cita estudo, amostra, tribunal ou período. E não há de onde tirar: para
# calcular "taxa de êxito por tese" seria preciso uma base que registrasse QUAL
# TESE foi suscitada em cada defesa e como cada uma foi decidida. Essa base não
# existe publicamente — nem no IBAMA, nem na PGFN, nem no CNJ.
#
# O que EXISTE, e foi medido: o IBAMA publica os julgamentos de auto de
# infração das 27 UFs. Os números de _BASE_EMPIRICA saíram desse arquivo, lidos
# na íntegra. Não substituem uma taxa por tese — medem outra coisa, e dizem
# qual. Mas são verificáveis, que é exatamente o que falta às outras.
_PROCEDENCIA_TAXAS = {
    "origem": ["ATLAS-IA (app React)", "ATLAS FORENSE v2.1"],
    "por_que": (
        "Nenhuma base pública registra qual tese de defesa foi suscitada em cada "
        "auto, nem como cada tese foi decidida. Logo, 'taxa de êxito por tese' não "
        "é calculável a partir de dado aberto, e estes percentuais não puderam ser "
        "confirmados em fonte primária. Antes de qualquer uso diante de cliente, "
        "devem ser validados pela advogada responsável ou substituídos por dado "
        "de acervo próprio."
    ),
}

# Medido em 261.976 julgamentos de auto de infração publicados pelo IBAMA nas
# 27 UFs (SICAFI · volumeJulgamentoAI), lidos na íntegra. 684 linhas malformadas
# foram descartadas; valores em Cruzeiro, Cruzado e BTN foram excluídos das
# razões, por não serem comparáveis a Real.
_BASE_EMPIRICA = {
    "fonte": "IBAMA — Dados Abertos, Julgamentos de Auto de Infração (SICAFI, 27 UFs)",
    "universo": 261976,
    "pagamento_mediano_sobre_o_valor_do_auto": "70,0%",
    "pagaram_cerca_de_70_por_cento": "40,1%",
    "pagaram_menos_que_o_auto": "78,5%",
    "pagaram_MAIS_que_o_auto": "18,8%",
    "extintos_por_prescricao": "2,09%",
    "cancelados": "1,78%",
    "ajuizados_ou_em_cobranca_judicial": "7,68%",
    "sem_data_de_julgamento_no_registro": "33,6%",
    "como_ler": (
        "Estas são taxas de DESFECHO sobre todos os autos julgados, não taxas de "
        "êxito de tese. O dado mais útil para dimensionar a conversa com o cliente "
        "é o pagamento mediano de 70,0% do valor do auto: é o que acontece sem "
        "defesa nenhuma, e portanto o piso contra o qual qualquer defesa deve ser "
        "comparada. A concentração exata em torno de 70% sugere desconto legal "
        "por pagamento — a base normativa deve ser confirmada pela advogada, "
        "não foi verificada aqui."
    ),
}


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
        # A PROCEDÊNCIA DA TAXA ACOMPANHA O NÚMERO, SEMPRE.
        #
        # Este campo existe porque o número acima é o mais perigoso que o
        # sistema produz. Ele é uma multiplicação da multa por um percentual —
        # e esse percentual NÃO tem fonte pública verificável.
        #
        # O catálogo declara a origem das taxas: os dois sistemas anteriores
        # (ATLAS-IA React e ATLAS FORENSE v2.1). Nenhum dos dois cita estudo,
        # amostra ou base. E não haveria de onde: nenhuma base pública
        # registra QUAL TESE foi suscitada em cada defesa, de modo que
        # "taxa de êxito por tese" não é calculável a partir de dado aberto.
        #
        # O número segue sendo exibido para ordenar teses entre si — para isso
        # ele serve. Não serve para ser lido como probabilidade de ganho, e
        # muito menos para virar promessa a cliente.
        "procedencia_da_taxa": {
            "origem": _PROCEDENCIA_TAXAS["origem"],
            "verificada_em_fonte_publica": False,
            "por_que": _PROCEDENCIA_TAXAS["por_que"],
            "uso_legitimo": ("Ordenar as teses entre si e dimensionar a conversa. "
                             "NÃO é probabilidade de êxito nem valor a receber."),
        },
        # O que é verificável fica ao lado, com a fonte.
        "referencia_verificada": _BASE_EMPIRICA,
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

    # Respostas que o motor não soube ler. Antes eram descartadas em silêncio:
    # um "sim"/"nao" no lugar de "ok"/"fail", ou um id de item digitado errado,
    # produzia um laudo perfeitamente formado com ZERO não conformidades — e
    # nada na resposta denunciava que as respostas tinham sido jogadas fora.
    # Num documento que vai para o cliente esse silêncio é o pior defeito
    # possível, porque o erro se parece exatamente com um resultado limpo.
    VOCABULARIO = ("ok", "fail", "na")
    ids_desconhecidos: list[str] = []
    valores_invalidos: list[dict] = []

    for item_id, resp in (respostas or {}).items():
        it = itens.get(item_id)
        if not it:
            ids_desconhecidos.append(item_id)
            continue
        if resp not in VOCABULARIO:
            valores_invalidos.append({"id": item_id, "valor_recebido": resp})
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
        # Sempre presente. Quando não está vazio, o resultado acima está
        # incompleto e NÃO deve ser entregue como laudo sem antes corrigir a
        # origem das respostas.
        "respostas_ignoradas": {
            "total": len(ids_desconhecidos) + len(valores_invalidos),
            "ids_fora_do_catalogo": ids_desconhecidos,
            "valores_fora_do_vocabulario": valores_invalidos,
            "vocabulario_aceito": list(VOCABULARIO),
        },
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
        # Repassado da auditoria: se houver resposta descartada, o laudo está
        # incompleto e quem o consome precisa saber ANTES de imprimir.
        "respostas_ignoradas": auditoria.get("respostas_ignoradas"),
        "laudo_integro": not (auditoria.get("respostas_ignoradas") or {}).get("total"),
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
