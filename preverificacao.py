"""
Pré-verificação do protocolo a partir do registro público do IBAMA.

O PROBLEMA QUE ISTO RESOLVE
---------------------------
O protocolo tem 60 itens e todos eram perguntados à pessoa, um a um, mesmo
quando a resposta já estava no registro público que o sistema baixa todo dia.
Medido sobre os 54.353 autos de 2023 a 2026 (não cancelados) do arquivo
`auto_infracao_csv.zip`: a base tem 84 colunas e o sistema lia 15.

A FRONTEIRA QUE NÃO PODE SER ATRAVESSADA
-----------------------------------------
O registro público é o CADASTRO ADMINISTRATIVO do auto — não é o auto, não é o
processo. Campo vazio no cadastro NÃO prova que a peça falta no processo.
Confundir as duas coisas produziria um laudo de aparência impecável e conteúdo
inventado, que é o pior desfecho possível para este produto.

Daí as três faixas, e a regra de cada uma:

  APURADO    conta de chegada sobre dado PRESENTE (subtração de datas,
             cruzamento da base). Não há leitura nem interpretação. Só isto
             vira resposta — e chega marcado como apurado, nunca confundido
             com o que a pessoa respondeu.

  EVIDÊNCIA  o registro carrega um fato que pesa no item. O sistema mostra o
             campo e o valor ao lado da pergunta; quem responde é a pessoa.

  INTOCADO   exige o processo na mão. Nada é sugerido, pré-marcado ou
             insinuado. É o silêncio deliberado.

Ausência no cadastro nunca vira afirmação sobre o processo. Quando a ausência
é ela própria o achado (não há coordenada nenhuma registrada), isso é dito
como ausência no registro, com essas palavras.
"""
from __future__ import annotations

import unicodedata
from datetime import date, timedelta  # noqa: F401  (timedelta usado nas notificações)
from typing import Optional

# ── vocabulário de resposta do catálogo ────────────────────────────────────
OK, FAIL, NA = "ok", "fail", "na"

# Janela usada no cruzamento do item 5.6. Trinta dias é o intervalo em que
# autuações sobre a mesma pessoa e o mesmo município deixam de parecer
# coincidência e passam a merecer conferência de bis in idem. Não é prazo
# legal: é critério de triagem, e está escrito na leitura de cada achado.
JANELA_MULTIPLAS_DIAS = 30

# Marco do art. 59 da Lei 12.651/12 — fatos anteriores a esta data podem ser
# alcançados pelo PRA.
MARCO_PRA = date(2008, 7, 22)

DECURSO_ANOS = 3


def _d(valor) -> Optional[date]:
    """
    Aceita date, datetime, string ISO (2026-05-28) ou string brasileira
    (28/05/2026); devolve date ou None.

    O formato brasileiro entrou porque o Sinaflor publica DD/MM/AAAA, e sem ele
    TODAS as 604 autorizações caíam no balde "janela não comparável" — a tela
    dizia "falta a data de um dos lados" com as duas datas presentes no arquivo.
    Afirmar que o dado falta quando ele existe é pior do que não exibir nada:
    transforma pergunta respondível em silêncio, que é justamente o que este
    sistema não pode fazer. Não há ambiguidade entre os dois formatos: o ISO
    começa por ano de quatro dígitos, o brasileiro por dia de dois.
    """
    if valor is None:
        return None
    if isinstance(valor, date):
        return valor
    s = str(valor).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        pass
    try:
        dia, mes, ano = s.split("/")
        return date(int(ano), int(mes), int(dia))
    except (ValueError, TypeError):
        return None


def _chave_lugar(nome) -> str:
    """
    Reduz nome de município à forma comparável: sem acento, sem caixa, sem
    espaço sobrando.

    Existe porque as duas bases escrevem o mesmo município de dois jeitos — o
    Sinaflor publica FEIJO e o cadastro do auto publica Feijó. A comparação
    ingênua respondia "NÃO, municípios diferentes" para o MESMO lugar, e esse
    campo é justamente o que a pessoa usa para decidir se a autorização tem a
    ver com o fato. Errar aqui é pior do que calar: manda descartar uma prova
    boa. A normalização só tira acento e caixa — não aproxima nomes parecidos,
    não adivinha abreviatura, não usa distância de edição.
    """
    s = unicodedata.normalize("NFKD", str(nome or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).strip().upper()


def _campo(reg: dict, nome: str) -> Optional[str]:
    v = (reg or {}).get(nome)
    if v is None:
        return None
    v = str(v).strip()
    return v or None


# ═══════════════════════════════════════════════════════════════════════════
#  FAIXA 1 — APURADO
# ═══════════════════════════════════════════════════════════════════════════

def _apurar(p, reg: dict, irmaos: list) -> dict:
    """
    Devolve {item_id: {resposta, porque, campos}} só para o que é conta de
    chegada. `irmaos` são os autos do mesmo documento/município na janela.
    """
    out: dict[str, dict] = {}
    fato, auto = _d(p.dt_fato), _d(p.dt_auto)

    # 6.1 — decurso entre o fato e a lavratura. Subtração pura.
    if fato and auto:
        dias = (auto - fato).days
        if dias >= 0:
            anos = dias / 365.25
            out["6.1"] = {
                "resposta": FAIL if anos > DECURSO_ANOS else OK,
                # "fail" aqui significa "a constatação do item se confirma",
                # que é como o catálogo lê a não conformidade.
                "porque": (
                    f"{dias} dias entre o fato ({fato.isoformat()}) e a lavratura "
                    f"({auto.isoformat()}) — {anos:.1f} ano(s)."
                ),
                "campos": {"DT_FATO_INFRACIONAL": fato.isoformat(),
                           "DAT_HORA_AUTO_INFRACAO": auto.isoformat()},
            }

        # 1.5 — inversão temporal. Só responde quando o auto antecede o fato:
        # aí a impossibilidade está na face do registro. No caso normal a
        # pergunta também indaga se as datas CONSTAM DO AUTO, o que o cadastro
        # não informa — então fica com a pessoa.
        else:
            out["1.5"] = {
                "resposta": FAIL,
                "porque": (
                    f"O auto foi lavrado {abs(dias)} dia(s) ANTES da data do fato "
                    f"registrada (auto {auto.isoformat()}, fato {fato.isoformat()})."
                ),
                "campos": {"DT_FATO_INFRACIONAL": fato.isoformat(),
                           "DAT_HORA_AUTO_INFRACAO": auto.isoformat()},
            }

    # 6.6 — o item é composto: fato anterior a 22/07/2008 E adesão ao PRA.
    #
    # Só a primeira metade é verificável no registro, e ela só resolve o item
    # numa direção: fato POSTERIOR ao marco elimina a hipótese inteira, e aí o
    # item é NÃO APLICÁVEL — o que o catálogo trata como fora da conta, sem
    # inflar nem desinflar o índice.
    #
    # Fato ANTERIOR ao marco não responde nada: a adesão ao PRA não está em
    # base nenhuma. Aí o item fica em branco e vira evidência. Responder "ok"
    # nos 96% de casos posteriores acrescentaria uma conformidade que ninguém
    # conferiu — exatamente o erro que este módulo existe para não cometer.
    if fato and fato >= MARCO_PRA:
        out["6.6"] = {
            "resposta": NA,
            "porque": (
                f"Fato em {fato.isoformat()}, posterior ao marco de "
                f"{MARCO_PRA.strftime('%d/%m/%Y')} — a hipótese do PRA não se coloca."
            ),
            "campos": {"DT_FATO_INFRACIONAL": fato.isoformat()},
        }

    # 1.10 — coordenada. Só responde a AUSÊNCIA, que é verificável. Presença
    # não prova datum SIRGAS 2000, que o cadastro não declara.
    if p.lat is None and p.lon is None and not _campo(reg, "DS_WKT"):
        out["1.10"] = {
            "resposta": FAIL,
            "porque": "Não há latitude, longitude nem geometria no registro público deste auto.",
            "campos": {"NUM_LATITUDE_AUTO": "(vazio)", "NUM_LONGITUDE_AUTO": "(vazio)",
                       "DS_WKT": "(vazio)"},
        }

    # 5.6 — múltiplas multas sobre o mesmo ato físico. Cruzamento da base, que
    # nenhuma pessoa faz lendo um processo de cada vez.
    if irmaos:
        lista = ", ".join(
            f"{i.num_auto} ({_d(i.dt_auto).isoformat() if _d(i.dt_auto) else 's/data'})"
            for i in irmaos[:8]
        )
        mais = f" e mais {len(irmaos) - 8}" if len(irmaos) > 8 else ""
        out["5.6"] = {
            "resposta": FAIL,
            "porque": (
                f"{len(irmaos)} outro(s) auto(s) contra o mesmo documento, no mesmo "
                f"município, em até {JANELA_MULTIPLAS_DIAS} dias: {lista}{mais}. "
                "Conferir no processo se tratam do mesmo ato físico."
            ),
            "campos": {"autos_proximos": str(len(irmaos))},
        }

    return out


# ═══════════════════════════════════════════════════════════════════════════
#  FAIXA 2 — EVIDÊNCIA
# ═══════════════════════════════════════════════════════════════════════════

def _ev(item, titulo, campos, leitura) -> dict:
    return {"item": item, "titulo": titulo,
            "campos": [{"nome": n, "valor": v} for n, v in campos if v],
            "leitura": leitura}


def _brl(v) -> str:
    try:
        return "R$ " + f"{float(v):,.2f}".replace(",", "·").replace(".", ",").replace("·", ".")
    except Exception:
        return "—"


def _evidencia_divida(d, escopo: Optional[str] = None) -> list[dict]:
    """
    Perfil do AUTUADO na Dívida Ativa da União.

    A RESSALVA VAI EM TODA EVIDÊNCIA, sem exceção: este perfil é do autuado,
    NÃO da multa deste auto. Varri as 134 receitas que a PGFN publica e nenhuma
    identifica multa do IBAMA — inclusive a que se chama "Contribuição Risco
    Ambiental", que é previdenciária. Sem essa frase ao lado do número, o
    analista leria "R$ 86 bilhões em dívida ativa" como se fosse deste processo.
    """
    if not d:
        return []
    ref = f" Base da PGFN com referência de {d.referencia_da_base}." if d.referencia_da_base else ""
    # A PGFN publica por estabelecimento. Quando o casamento foi pela raiz, o
    # número é do GRUPO e não daquele CNPJ — dizer isso é obrigatório.
    de_quem = ("de OUTRO estabelecimento do mesmo grupo econômico (mesma raiz de CNPJ), "
               "não deste CNPJ" if escopo == "grupo" else "deste CNPJ")
    RESSALVA = (f"Perfil {de_quem} na Dívida Ativa da União — NÃO da multa deste auto. "
                "A base da PGFN não identifica multas do IBAMA entre as receitas que "
                "publica." + ref)
    ev: list[dict] = []

    # 7.4 — redirecionamento para sócios ou terceiros.
    vinculados = (d.corresponsavel or 0) + (d.solidario or 0)
    if vinculados:
        ev.append(_ev("7.4", f"{vinculados} inscrição(ões) com terceiro vinculado à dívida",
            [("CORRESPONSAVEL", str(d.corresponsavel or 0)),
             ("SOLIDARIO", str(d.solidario or 0)),
             ("INSCRICOES", str(d.inscricoes or 0))],
            "Há corresponsável ou devedor solidário registrado em dívidas federais deste "
            "autuado — base factual para discutir redirecionamento. " + RESSALVA))

    # 7.5 e 6.3 — execução fiscal em curso.
    if d.ajuizadas:
        ev.append(_ev("7.5", f"{d.ajuizadas} de {d.inscricoes} inscrições já ajuizadas",
            [("INDICADOR_AJUIZADO", f"{d.ajuizadas} SIM"),
             ("inscricao_mais_antiga", d.inscricao_mais_antiga or "—")],
            "O autuado já figura em execução fiscal da União. " + RESSALVA))
        if d.inscricao_mais_antiga:
            ev.append(_ev("6.3", f"Inscrição mais antiga em {d.inscricao_mais_antiga}",
                [("inscricao_mais_antiga", d.inscricao_mais_antiga),
                 ("inscricao_mais_recente", d.inscricao_mais_recente or "—")],
                "Marco temporal do endividamento federal do autuado. Não é a inscrição "
                "desta multa. " + RESSALVA))

    # 7.6 — porte da dívida e transação em curso.
    sit = d.situacoes or {}
    beneficio = sum(v for k, v in sit.items() if "benef" in str(k).lower())
    ev.append(_ev("7.6", f"Dívida ativa federal total: {_brl(d.valor_total)}",
        [("VALOR_CONSOLIDADO", _brl(d.valor_total)),
         ("INSCRICOES", str(d.inscricoes or 0)),
         ("situações", ", ".join(f"{k}: {v}" for k, v in sit.items()) or "—")],
        (f"{beneficio} inscrição(ões) em benefício fiscal — há parcelamento ou transação "
         f"em curso, o que informa capacidade de pagamento. " if beneficio else
         "Sem inscrição em benefício fiscal registrada. ") + RESSALVA))

    return ev


def _evidencia_notificacao(notifs: list, dt_auto) -> list[dict]:
    """
    Notificações do MESMO PROCESSO administrativo do auto.

    O vínculo é o número do processo, e só ele. Notificação do mesmo CPF/CNPJ
    noutro processo cobre 22% da carteira contra 8,3% do vínculo por processo —
    mas seria outro documento, de outro caso, exibido ao lado de uma pergunta
    sobre este. Cobertura maior não compra nada quando o que ela acrescenta
    está errado.

    A comparação de datas aqui carrega uma correção importante. Confrontar a
    lavratura com o vencimento do prazo da notificação acusava dois terços dos
    autos. Era artefato: 558 dos 951 pares auto × notificação da carteira
    (58,7%) são do MESMO DIA, lados de uma mesma fiscalização — a notificação
    impondo obrigação futura, o auto punindo fato passado. O apontamento de
    prazo só existe quando o auto vem DEPOIS da notificação e ainda assim antes
    de o prazo concedido vencer: 30 autos, 3,4% dos 893 que têm notificação.
    Um segundo apontamento, de natureza diferente, cobre 46 autos (5,2%): o
    auto é ANTERIOR à notificação, o que é questão de ordem dos atos e não de
    prazo. Os dois são exibidos com redações distintas, e nunca somados.
    """
    if not notifs:
        return []
    ev: list[dict] = []
    base = _d(dt_auto)

    for n in notifs[:4]:
        dn = _d(getattr(n, "dat_notificacao", None))
        try:
            prazo = int(float(getattr(n, "prazo_apresentacao", None) or 0))
        except (TypeError, ValueError):
            prazo = 0

        linhas = [("NUM_NOTIFICACAO", getattr(n, "num_notificacao", None)),
                  ("DAT_NOTIFICACAO", getattr(n, "dat_notificacao", None)),
                  ("PRAZO_APRESENTACAO", f"{prazo} dia(s)" if prazo else None),
                  ("FORMA_ENTREGA", getattr(n, "forma_entrega", None)),
                  ("SIT_ATENDIDA", getattr(n, "sit_atendida", None)),
                  ("DES_OCORRENCIA", getattr(n, "des_ocorrencia", None))]

        leitura = ("Notificação do mesmo processo administrativo deste auto. "
                   "O texto acima é a exigência feita pelo órgão antes da autuação.")

        if base and dn and prazo > 0:
            dias = (base - dn).days
            venc = dn + timedelta(days=prazo)
            if dias == 0:
                leitura += (" Notificação e auto são do MESMO DIA — provavelmente a mesma "
                            "fiscalização, com a notificação impondo obrigação futura e o "
                            "auto punindo fato passado. Não há aqui apontamento de prazo.")
            elif 0 < dias < prazo:
                leitura += (f" ATENÇÃO: o auto foi lavrado {dias} dia(s) depois da "
                            f"notificação, com o prazo concedido vencendo só em "
                            f"{venc.isoformat()} — ou seja, {(venc - base).days} dia(s) "
                            "antes de o administrado esgotar o prazo que o próprio órgão "
                            "lhe deu. Confira no processo se a exigência já havia sido "
                            "cumprida ou dispensada.")
            elif dias < 0:
                leitura += (f" O auto é {abs(dias)} dia(s) ANTERIOR à notificação — "
                            "confira a ordem dos atos no processo.")

        ev.append(_ev("3.1", f"Notificação {getattr(n, 'num_notificacao', '') or ''} "
                             f"no mesmo processo", linhas, leitura))

    if len(notifs) > 4:
        ev.append(_ev("3.1", f"Mais {len(notifs) - 4} notificação(ões) no mesmo processo",
                      [], "O processo acumula outras notificações — confira a sequência "
                          "de atos nas peças."))
    return ev


def _area(valor) -> Optional[float]:
    """Área em hectares, tolerando vírgula decimal e separador de milhar."""
    if valor is None:
        return None
    s = str(valor).strip().replace(".", "").replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v > 0 else None


def _ha(v: float) -> str:
    return f"{v:,.4f}".replace(",", "·").replace(".", ",").replace("·", ".").rstrip("0").rstrip(",") + " ha"


def _evidencia_termo(termos: list, reg: dict) -> list[dict]:
    """
    Termos lavrados na mesma fiscalização: embargo, apreensão, suspensão.

    O vínculo é o NUM_AUTO_INFRACAO declarado pelo próprio IBAMA no termo —
    sem inferência nenhuma, ao contrário da notificação, que só casa pelo
    processo.

    A ÁREA É O MOTIVO DE ESTA FONTE EXISTIR
    ----------------------------------------
    QT_AREA consta em 7,4% da carteira; QTD_AREA_EMBARGADA, em 91,5% dos
    embargos. São 1.444 autos cuja área só aparece no termo — 93,2% deles
    descrevendo desmatamento, onde o número é a base do cálculo da multa.

    Antes de exibir esse número foi preciso saber se ele é a mesma grandeza.
    Nos 703 autos com as duas áreas, elas são idênticas em 698 (99,3%). Logo:
    o termo PREENCHE A LACUNA do cadastro, mas não confirma coisa alguma — é
    a mesma fonte estatal publicada duas vezes, e a leitura de cada evidência
    diz isso com todas as letras. Quando os dois números existem e divergem,
    o que se mostra é a divergência, não uma conclusão sobre ela.
    """
    if not termos:
        return []
    ev: list[dict] = []
    area_auto = _area(_campo(reg, "QT_AREA"))

    embargos = [t for t in termos if (getattr(t, "tipo", "") or "") == "embargo"]
    outros = [t for t in termos if t not in embargos]

    # ── 1. A área ───────────────────────────────────────────────────────────
    area_emb = sum(_area(getattr(t, "area", None)) or 0.0 for t in embargos)
    if area_emb > 0:
        nums = ", ".join(str(getattr(t, "num_termo", "") or "") for t in embargos if getattr(t, "num_termo", None))
        linhas = [("QTD_AREA_EMBARGADA (termo de embargo)", _ha(area_emb)),
                  ("QT_AREA (cadastro do auto)", _ha(area_auto) if area_auto else "— vazio no cadastro"),
                  ("TERMO(S) DE EMBARGO", nums),
                  ("TIPO_AREA", "; ".join(sorted({(getattr(t, "tipo_area", "") or "").strip()
                                                  for t in embargos if getattr(t, "tipo_area", None)})) or None)]
        if area_auto is None:
            leitura = ("A área NÃO consta do cadastro do auto, mas consta do termo de embargo "
                       "lavrado na mesma fiscalização. Em infração de desmatamento a área é a "
                       "base do cálculo do valor. ATENÇÃO à procedência: este número é do TERMO, "
                       "não do auto, e vem da mesma fonte estatal — não confirma o cálculo da "
                       "multa, apenas mostra qual área o próprio órgão registrou. Confira no "
                       "processo qual área foi efetivamente usada na dosimetria.")
        elif abs(area_emb - area_auto) <= max(area_auto * 0.01, 0.0001):
            leitura = ("As duas áreas publicadas pelo IBAMA para este auto coincidem. Coincidir "
                       "não é confirmar: é a mesma fonte estatal publicada duas vezes, não uma "
                       "segunda medição. Serve para descartar erro de transcrição, nada além.")
        else:
            dif = area_emb - area_auto
            leitura = (f"DIVERGÊNCIA: o próprio IBAMA publicou duas áreas diferentes para este "
                       f"mesmo auto — {_ha(area_auto)} no cadastro do auto e {_ha(area_emb)} no "
                       f"termo de embargo, diferença de {_ha(abs(dif))} "
                       f"({'a maior' if dif > 0 else 'a menor'} no termo). Na carteira medida isso "
                       f"ocorre em 0,7% dos casos com as duas áreas. Sendo a área a base do "
                       f"cálculo, confira no processo qual número sustentou o valor da multa.")
        ev.append(_ev("4.9", "Área: cadastro do auto × termo de embargo", linhas, leitura))

        if area_auto is None:
            ev.append(_ev("5.2", "Base de cálculo ausente no auto, presente no termo",
                          [("QT_AREA (cadastro do auto)", "— vazio"),
                           ("QTD_AREA_EMBARGADA (termo)", _ha(area_emb))],
                          "O valor da multa por hectare depende de uma área que o cadastro do "
                          "auto não traz. O termo da mesma fiscalização traz. Número do termo, "
                          "não do auto — a memória de cálculo continua sendo peça do processo."))

    # ── 2. O embargo está em vigor? ─────────────────────────────────────────
    for t in embargos[:3]:
        desemb = (getattr(t, "sit_desembargo", "") or "").strip().upper()
        linhas = [("NUM_TAD", getattr(t, "num_termo", None)),
                  ("DAT_EMBARGO", getattr(t, "data", None)),
                  ("SIT_DESEMBARGO", desemb or "— sem registro de desembargo"),
                  ("DAT_DESEMBARGO", getattr(t, "dat_desembargo", None)),
                  ("DES_DESEMBARGO", getattr(t, "des_desembargo", None)),
                  ("DES_LOCALIZACAO", getattr(t, "localizacao", None)),
                  ("DES_TAD", getattr(t, "descricao", None))]
        if desemb == "S":
            leitura = ("O registro traz DESEMBARGO para este termo. A área deixou de estar "
                       "interditada segundo o cadastro — confira a decisão que o motivou, que "
                       "é peça do processo.")
        else:
            leitura = ("O cadastro não registra desembargo: pelo registro público, a interdição "
                       "segue em vigor. Isso muda a urgência prática do caso — a área continua "
                       "impedida de uso — e alcança a via do PRAD. Na carteira medida, apenas "
                       "0,6% dos embargos têm desembargo registrado. Ausência no cadastro não "
                       "prova ausência no processo: confira se há decisão posterior.")
        ev.append(_ev("8.3", f"Termo de embargo {getattr(t, 'num_termo', '') or ''} — situação",
                      linhas, leitura))

    # ── 3. Os demais termos da mesma fiscalização ───────────────────────────
    ROTULO = {"apreensao": "Termo de apreensão", "suspensao": "Termo de suspensão",
              "demolicao": "Termo de demolição"}
    for t in outros[:4]:
        tipo = (getattr(t, "tipo", "") or "").strip()
        linhas = [("NUM_TAD", getattr(t, "num_termo", None)),
                  ("DATA", getattr(t, "data", None)),
                  ("VALOR", getattr(t, "valor", None)),
                  ("FORMA_ENTREGA", getattr(t, "forma_entrega", None)),
                  ("DES_TAD", getattr(t, "descricao", None)),
                  ("DES_JUSTIFICATIVA", getattr(t, "justificativa", None)),
                  ("DES_LOCALIZACAO", getattr(t, "localizacao", None))]
        leitura = ("Termo lavrado na mesma fiscalização deste auto, vinculado pelo próprio "
                   "número do auto no registro do IBAMA. O texto acima é o que o órgão "
                   "determinou. Se houve bem apreendido, a destinação, o depositário e o estado "
                   "de conservação são peças do processo — o cadastro não os traz.")
        ev.append(_ev("8.3", f"{ROTULO.get(tipo, 'Termo')} {getattr(t, 'num_termo', '') or ''}",
                      linhas, leitura))

    # ── 4. Ordem de fiscalização do termo × do auto ─────────────────────────
    ordem_auto = _campo(reg, "NUM_ORDEM_FISCALIZACAO") or _campo(reg, "ORDEM_FISCALIZACAO")
    ordens = sorted({(getattr(t, "num_ordem_fiscalizacao", "") or "").strip()
                     for t in termos if getattr(t, "num_ordem_fiscalizacao", None)})
    if ordens:
        divergem = ordem_auto and all(o != ordem_auto for o in ordens)
        ev.append(_ev("1.12", "Ordem de fiscalização: auto × termo",
                      [("ORDEM no auto", ordem_auto or "— vazia no cadastro"),
                       ("ORDEM no(s) termo(s)", "; ".join(ordens)),
                       ("UNID_ORDENADORA", "; ".join(sorted({(getattr(t, "unid_ordenadora", "") or "").strip()
                                                             for t in termos
                                                             if getattr(t, "unid_ordenadora", None)})) or None)],
                      ("As ordens de fiscalização do auto e do termo NÃO coincidem. Podem ser "
                       "atos de diligências distintas — confira no processo qual ordem autorizou "
                       "cada lavratura." if divergem else
                       "Ordem de fiscalização registrada no termo da mesma diligência. Serve "
                       "para localizar no processo a autorização que amparou a ação.")))
    return ev


def _evidencia_uc(uc) -> list[dict]:
    """
    Auto cuja coordenada cai dentro de Unidade de Conservação federal.

    Primeira fonte do sistema que casa por POSIÇÃO, não por número nem por
    documento: a coordenada do auto testada contra os 347 polígonos do ICMBio.

    O limite vai escrito em toda evidência, porque ele é real: o ponto testado
    é a coordenada que o IBAMA registrou, não o perímetro da área autuada.
    Ponto dentro não prova que toda a área está dentro; ponto fora não prova
    que nada está. E a camada não traz zona de amortecimento — ausência aqui
    não é ausência de UC por perto.
    """
    if not uc:
        return []
    grupo = (getattr(uc, "grupo", "") or "").strip()
    integral = grupo.lower().startswith("prote")
    linhas = [("UNIDADE DE CONSERVAÇÃO", getattr(uc, "nome_uc", None)),
              ("GRUPO", grupo or None),
              ("CNUC", getattr(uc, "cnuc", None)),
              ("ESFERA", getattr(uc, "esfera", None)),
              ("BIOMA", getattr(uc, "bioma", None)),
              ("ATO DE CRIAÇÃO", getattr(uc, "ato_criacao", None)),
              ("FONTE", "ICMBio — limites oficiais, camada de ago/2026")]

    base = ("A coordenada registrada no auto cai DENTRO dos limites oficiais desta "
            "unidade de conservação federal. ")
    if integral:
        leitura = base + (
            "É unidade de PROTEÇÃO INTEGRAL — Parque Nacional, Reserva Biológica ou "
            "Estação Ecológica não admitem as mesmas atividades que uma área de uso "
            "sustentável. Isso alcança tipificação e competência, e muda a conversa "
            "sobre o caso. Na carteira medida, só 26 autos estão nesta situação.")
    else:
        leitura = base + (
            "É unidade de USO SUSTENTÁVEL — a categoria admite atividades, dentro do "
            "que o plano de manejo e o ato de criação permitem. O que vale é o regime "
            "desta unidade, que é peça a consultar, não um dado de cadastro.")
    leitura += (" LIMITE DO CRUZAMENTO: o que foi testado é o PONTO do auto, não o "
                "perímetro da área autuada — ponto dentro não prova que toda a área "
                "está dentro. Zona de amortecimento não consta desta camada.")
    return [_ev("2.3", "Localização dentro de unidade de conservação federal", linhas, leitura)]


def _evidencia_autorizacao(autorizacoes: list, p) -> list[dict]:
    """
    Autorizações de supressão do CNPJ autuado — item 2.1.

    O item 2.1 é determinante, peso 10, e chegava em branco. Esta é a primeira
    fonte que o alcança.

    A RESSALVA É A PRÓPRIA RAZÃO DE SER DESTA EVIDÊNCIA. O vínculo aqui é o
    CNPJ do detentor, não o número do auto. Autorização do mesmo CNPJ NÃO é
    necessariamente a autorização deste fato — pode ser de outro imóvel, outro
    município, outro período. Por isso o que se exibe é a autorização com a
    janela de validade e o município AO LADO da data e do município do auto,
    para a pessoa comparar. O sistema não conclui nada.
    """
    if not autorizacoes:
        return []
    dt_fato = _d(getattr(p, "dt_fato", None)) or _d(getattr(p, "dt_auto", None))
    mun_auto = (getattr(p, "municipio", "") or "").strip()

    # Quatro situações, não três. A autorização emitida DEPOIS da data do fato
    # tinha ido parar em "janela não comparável", e não é isso: a janela é
    # perfeitamente comparável e a resposta é que ela não cobria o fato. São
    # coisas opostas — uma diz "não sei", a outra diz "sei, e é posterior" —,
    # e a posterior costuma ser a regularização feita depois da autuação, que
    # é assunto de dosimetria, não de licitude da conduta.
    vigentes, vencidas, posteriores, outras = [], [], [], []
    for a in autorizacoes:
        emi, val = _d(getattr(a, "data_emissao", None)), _d(getattr(a, "data_validade", None))
        if dt_fato and emi and val and emi <= dt_fato <= val:
            vigentes.append((a, emi, val))
        elif dt_fato and val and val < dt_fato:
            vencidas.append((a, emi, val))
        elif dt_fato and emi and emi > dt_fato:
            posteriores.append((a, emi, val))
        else:
            outras.append((a, emi, val))

    ev: list[dict] = []
    RESSALVA = (" ATENÇÃO À PROCEDÊNCIA: esta autorização é do CNPJ do autuado, não "
                "necessariamente DESTE fato. O vínculo é o documento, não o número do "
                "auto — pode ser de outro imóvel, outro município ou outro período. "
                "Compare o município e a data antes de usar.")

    # Mais recente primeiro dentro de cada balde: entre autorizações do mesmo
    # CNPJ, a que venceu ontem diz mais sobre o caso do que a de 2015.
    for lista in (vigentes, vencidas, posteriores, outras):
        lista.sort(key=lambda t: (t[2] or date.min, t[1] or date.min), reverse=True)

    mostradas = 0

    def bloco(titulo, lista, leitura):
        nonlocal mostradas
        mostradas += min(len(lista), 3)
        for a, emi, val in lista[:3]:
            mun_aut = (getattr(a, "municipio", "") or "").strip()
            mesmo_mun = (mun_auto and mun_aut
                         and _chave_lugar(mun_auto) == _chave_lugar(mun_aut))
            linhas = [("NRO_AUTORIZACAO", getattr(a, "nro_autorizacao", None)),
                      # SITUACAO é o estado ATUAL no Sinaflor; a janela abaixo é a
                      # comparação com a DATA DO FATO. Uma autorização vigente na
                      # data do fato aparece hoje como "Vencida" sem contradição
                      # alguma — e é confusão fácil de fazer, por isso vai rotulado.
                      ("SITUACAO (hoje, no Sinaflor)", getattr(a, "situacao", None)),
                      ("VALIDADE", f"{emi.isoformat() if emi else '?'} a {val.isoformat() if val else '?'}"),
                      ("DATA DO FATO (auto)", dt_fato.isoformat() if dt_fato else "— sem data"),
                      ("MUNICÍPIO da autorização", mun_aut or None),
                      ("MUNICÍPIO do auto", mun_auto or None),
                      # Sem um dos dois nomes não se diz "não": diz-se que falta o dado.
                      ("MESMO MUNICÍPIO?",
                       "sim" if mesmo_mun else
                       ("NÃO — confira se é o mesmo imóvel" if (mun_auto and mun_aut)
                        else "— não dá para comparar: falta o município de um dos lados")),
                      ("FINALIDADE", getattr(a, "finalidade", None)),
                      ("AREA_TOTAL_PROJ", getattr(a, "area_total", None)),
                      ("IMÓVEL / CAR", " · ".join(x for x in [(getattr(a, "imovel", "") or ""),
                                                              (getattr(a, "car", "") or "")] if x) or None)]
            ev.append(_ev("2.1", titulo, linhas, leitura + RESSALVA))

    bloco("Autorização de supressão VIGENTE na data do fato", vigentes,
          "O Sinaflor registra autorização de supressão do CNPJ autuado cuja janela de "
          "validade ESTAVA ABERTA na data do fato. O campo SITUACAO acima é o estado de "
          "hoje e pode dizer 'Vencida' sem contradizer isto. Se for do mesmo imóvel, é "
          "matéria central da defesa: a conduta pode estar amparada por ato do próprio "
          "órgão.")
    bloco("Autorização de supressão VENCIDA antes do fato", vencidas,
          "O CNPJ autuado TINHA autorização, e a janela de validade fechou ANTES da data "
          "do fato. Isso é situação diferente de nunca ter tido: alcança a discussão "
          "sobre boa-fé e sobre a dosimetria.")
    bloco("Autorização de supressão EMITIDA DEPOIS do fato", posteriores,
          "A autorização é POSTERIOR à data do fato: não amparava a conduta autuada. "
          "Não é 'não sei' — é 'sei, e não cobria'. Costuma ser regularização feita "
          "depois da autuação, o que alcança dosimetria e boa-fé, não a licitude da "
          "conduta. Confira no processo se houve pedido anterior em análise.")
    bloco("Autorização de supressão do mesmo CNPJ (janela não comparável)", outras,
          "O Sinaflor registra autorização do CNPJ autuado, mas as datas não permitem "
          "dizer se estava vigente na data do fato — falta a data de um dos lados, ou "
          "o próprio auto não traz data do fato.")

    # O resto conta a partir do que REALMENTE foi exibido, não de um número fixo:
    # cada balde mostra até três, então o total exibido varia de 0 a 9.
    restantes = len(autorizacoes) - mostradas
    if restantes > 0:
        ev.append(_ev("2.1", f"Mais {restantes} autorização(ões) do mesmo CNPJ",
                      [("VIGENTES na data do fato", len(vigentes) or None),
                       ("VENCIDAS antes do fato", len(vencidas) or None),
                       ("EMITIDAS depois do fato", len(posteriores) or None),
                       ("sem janela comparável", len(outras) or None)],
                      "O CNPJ acumula outras autorizações no Sinaflor. Acima estão as "
                      "mais recentes de cada situação; vale varrer a lista completa "
                      "antes de afirmar ausência de amparo." + RESSALVA))
    return ev


def _evidenciar(p, reg: dict, irmaos_todos: list) -> list[dict]:
    ev: list[dict] = []
    g = lambda n: _campo(reg, n)

    # 1.3 — dispositivo × conduta, lado a lado.
    enq = g("DS_ENQUADRAMENTO_ADMINISTRATIVO") or g("DS_ENQUADRAMENTO_NAO_ADMINISTRATIVO")
    desc = g("DES_AUTO_INFRACAO")
    if enq or desc:
        ev.append(_ev("1.3", "Dispositivo citado e conduta descrita",
            [("DS_ENQUADRAMENTO_ADMINISTRATIVO", g("DS_ENQUADRAMENTO_ADMINISTRATIVO")),
             ("DS_ENQUADRAMENTO_NAO_ADMINISTRATIVO", g("DS_ENQUADRAMENTO_NAO_ADMINISTRATIVO")),
             ("DS_ENQUADRAMENTO_COMPLEMENTAR", g("DS_ENQUADRAMENTO_COMPLEMENTAR")),
             ("DES_AUTO_INFRACAO", desc),
             ("DES_INFRACAO", g("DES_INFRACAO"))],
            "Compare o artigo enquadrado com a conduta que o próprio auto descreve."))

    # 1.2 — especificidade da descrição.
    if desc:
        ev.append(_ev("1.2", "Descrição da conduta no registro",
            [("DES_AUTO_INFRACAO", desc)],
            f"{len(desc)} caracteres. Avalie se descreve conduta específica ou repete a lei."))

    # 1.12 — ordem de fiscalização.
    if g("ORDEM_FISCALIZACAO") or g("UNID_ORDENADORA"):
        ev.append(_ev("1.12", "Ordem de fiscalização registrada",
            [("ORDEM_FISCALIZACAO", g("ORDEM_FISCALIZACAO")),
             ("UNID_ORDENADORA", g("UNID_ORDENADORA"))],
            "O cadastro registra a ordem que autorizou a diligência. Confira se a OS está juntada."))
    else:
        ev.append(_ev("1.12", "Sem ordem de fiscalização no registro", [],
            "O cadastro NÃO traz ordem de fiscalização para este auto — presente em 99,3% "
            "dos autos recentes. Ausência no cadastro não prova ausência no processo."))

    # 2.3 e 2.4 — unidade de conservação e classificação da área.
    if g("UNIDADE_CONSERVACAO") or g("CLASSIFICACAO_AREA"):
        ev.append(_ev("2.3", "Área e unidade de conservação",
            [("UNIDADE_CONSERVACAO", g("UNIDADE_CONSERVACAO")),
             ("CLASSIFICACAO_AREA", g("CLASSIFICACAO_AREA")),
             ("DS_BIOMAS_ATINGIDOS", p.bioma)],
            "Define competência e tipificação. UC federal consta em apenas 0,4% dos autos."))

    # 3.1 a 3.4 — notificação.
    forma, ciencia = g("FORMA_ENTREGA"), _d(p.dt_ciencia)
    if forma or ciencia:
        ev.append(_ev("3.1", "Como a notificação foi entregue",
            [("FORMA_ENTREGA", forma),
             ("DAT_CIENCIA_AUTUACAO", ciencia.isoformat() if ciencia else None)],
            {"Representante": "Entregue a representante — confira a procuração nos autos.",
             "Edital": "Notificação por edital — confira a tentativa prévia de AR frustrada.",
             "Correios": "Entrega por Correios — confira quem assinou o AR.",
             "Pessoalmente": "Entrega pessoal — confira a identificação de quem recebeu.",
             }.get(forma or "", "Confira o comprovante de entrega no processo.")))
    if not ciencia:
        ev.append(_ev("3.4", "Sem data de ciência no registro", [],
            "O cadastro não traz data de ciência — ausente em 31,9% dos autos recentes. "
            "Sem esse marco não há como conferir a contagem do prazo de defesa pelo registro."))

    # 4.2 — campo ou imagem.
    if g("TIPO_ACAO") or g("DS_REFERENCIA_ACAO_FISCALIZATORIA") or g("TP_ORIGEM_GE_AREA_AUTUADA"):
        ev.append(_ev("4.2", "Natureza da ação fiscalizatória",
            [("TIPO_ACAO", g("TIPO_ACAO")),
             ("OPERACAO", g("OPERACAO")),
             ("DS_REFERENCIA_ACAO_FISCALIZATORIA", g("DS_REFERENCIA_ACAO_FISCALIZATORIA")),
             ("TP_ORIGEM_GE_AREA_AUTUADA", g("TP_ORIGEM_GE_AREA_AUTUADA"))],
            "Indica o contexto da fiscalização. Não substitui o relatório de vistoria."))

    # 4.9 e 5.2 — área e cálculo.
    qt, infra = g("QT_AREA"), g("INFRACAO_AREA")
    if qt:
        ev.append(_ev("4.9", "Área no registro",
            [("QT_AREA", qt), ("INFRACAO_AREA", infra),
             ("WKT_GE_AREA_AUTUADA", "presente" if g("WKT_GE_AREA_AUTUADA") else None)],
            "Confira se a área do auto coincide com a que serviu de base ao cálculo."))
    elif (infra or "").lower() == "desmatamento":
        ev.append(_ev("4.9", "Auto de desmatamento SEM área no registro", [("INFRACAO_AREA", infra)],
            "A multa de desmatamento é calculada por hectare e o campo de área está vazio. "
            "Ocorre em 80,1% dos autos de desmatamento — confira o cálculo no processo."))
    if g("DS_ERRO_GE_AREA_AUTUADA"):
        ev.append(_ev("4.9", "O IBAMA registrou ERRO na geometria da área autuada",
            [("DS_ERRO_GE_AREA_AUTUADA", g("DS_ERRO_GE_AREA_AUTUADA"))],
            "Consta em apenas 0,1% dos autos. É o próprio órgão anotando defeito na área."))

    # 5.1 — dosimetria: o que consta e, sobretudo, o que falta.
    criterios = [("GRAVIDADE_INFRACAO", g("GRAVIDADE_INFRACAO")),
                 ("MOTIVACAO_CONDUTA", g("MOTIVACAO_CONDUTA")),
                 ("EFEITO_MEIO_AMBIENTE", g("EFEITO_MEIO_AMBIENTE")),
                 ("EFEITO_SAUDE_PUBLICA", g("EFEITO_SAUDE_PUBLICA"))]
    vazios = [n for n, v in criterios if not v]
    ev.append(_ev("5.1", "Critérios de dosimetria no registro", criterios,
        ("Todos os critérios do cadastro estão preenchidos."
         if not vazios else
         "Em branco no registro: " + ", ".join(vazios)
         + ". A gravidade falta em 65,1% dos autos recentes. "
           "Confira se o auto explicita os cinco critérios do art. 4º do Dec. 6.514/08.")))

    # 5.2 — fundamentação do valor.
    if g("FUNDAMENTACAO_MULTA") or g("DS_FATOR_AJUSTE") or g("TIPO_MULTA"):
        ev.append(_ev("5.2", "Fundamentação do valor",
            [("FUNDAMENTACAO_MULTA", g("FUNDAMENTACAO_MULTA")),
             ("DS_FATOR_AJUSTE", g("DS_FATOR_AJUSTE")),
             ("TIPO_MULTA", g("TIPO_MULTA"))],
            "Texto com que o órgão justificou o valor. Confira contra o cálculo discriminado."))

    # 5.3 — antecedentes, do próprio acervo.
    if irmaos_todos:
        ev.append(_ev("5.3", f"{len(irmaos_todos)} outro(s) auto(s) do mesmo documento na carteira",
            [("autos", ", ".join(i.num_auto for i in irmaos_todos[:10]))],
            "Base factual para discutir — ou afastar — reincidência. Só vale se houver "
            "decisão definitiva anterior, o que o cadastro não informa."))

    # 6.2 — marcos do ato inequívoco.
    ini, fim = g("DT_INICIO_ATO_INEQUIVOCO"), g("DT_FIM_ATO_INEQUIVOCO")
    if ini or fim:
        ev.append(_ev("6.2", "Marcos do ato inequívoco de apuração",
            [("DT_INICIO_ATO_INEQUIVOCO", ini), ("DT_FIM_ATO_INEQUIVOCO", fim)],
            "São os marcos que o cadastro registra para a apuração. Não substituem o "
            "andamento do processo, onde a paralisação de fato é verificada."))

    # 6.6 — quando o fato antecede o marco do PRA, o apurador se cala e o
    # achado vem como evidência: a adesão ao PRA não existe em base pública.
    fato = _d(p.dt_fato)
    if fato and fato < MARCO_PRA:
        ev.append(_ev("6.6", "Fato anterior ao marco do PRA",
            [("DT_FATO_INFRACIONAL", fato.isoformat())],
            f"O fato é de {fato.strftime('%d/%m/%Y')}, anterior a "
            f"{MARCO_PRA.strftime('%d/%m/%Y')}. Confira no processo se o imóvel aderiu "
            "ao Programa de Regularização Ambiental — isso não consta de base pública."))

    # 8.3 — recuperação.
    if g("PASSIVEL_RECUPERACAO"):
        s = g("PASSIVEL_RECUPERACAO")
        ev.append(_ev("8.3", "Marcação de passível de recuperação",
            [("PASSIVEL_RECUPERACAO", s)],
            "O IBAMA marcou a área como passível de recuperação — abre a via do PRAD."
            if s.upper() == "S" else
            "O IBAMA NÃO marcou a área como passível de recuperação."))

    # 9.1 e 9.2 — recurso.
    if g("SOLICITACAO_RECURSO"):
        ev.append(_ev("9.1", "Solicitação de recurso protocolada",
            [("SOLICITACAO_RECURSO", g("SOLICITACAO_RECURSO"))],
            "Há protocolo de recurso no cadastro. Confira se o conhecimento foi "
            "condicionado a depósito, caução ou arrolamento."))

    # 1.1 — identificação.
    ev.append(_ev("1.1", "Identificação no registro público",
        [("NOME_INFRATOR", "consta" if p.nome else None),
         ("CPF_CNPJ_INFRATOR", p.documento_mascarado),
         ("TP_PESSOA_INFRATOR", p.tipo_pessoa),
         ("MUNICIPIO / UF", f"{p.municipio or '—'}/{p.uf or '—'}")],
        "O cadastro traz a identificação. O endereço do auto não consta do registro "
        "público — confira nas peças."))

    return ev


# ═══════════════════════════════════════════════════════════════════════════
#  ENTRADA
# ═══════════════════════════════════════════════════════════════════════════

def pre_verificar(p, irmaos_janela: list, irmaos_todos: list,
                  divida=None, escopo_divida: Optional[str] = None,
                  notificacoes: Optional[list] = None,
                  termos: Optional[list] = None,
                  uc=None, autorizacoes: Optional[list] = None,
                  julgamento=None) -> dict:
    """
    p              — o Prospecto em análise
    irmaos_janela  — autos do mesmo documento e município em até 30 dias
    irmaos_todos   — todos os demais autos do mesmo documento na carteira
    divida         — linha de DividaAtiva do autuado, se houver
    escopo_divida  — "estabelecimento" (CNPJ inteiro) ou "grupo" (raiz)
    notificacoes   — notificações do MESMO processo administrativo
    termos         — embargo/apreensão/suspensão do MESMO número de auto
    uc             — linha de AutoEmUC, quando a coordenada cai dentro de UC federal
    autorizacoes   — autorizações do Sinaflor do MESMO CNPJ (não do mesmo auto)
    julgamento     — desfecho do auto no SICAFI, quando já julgado
    """
    reg = getattr(p, "registro", None) or {}
    apurados = _apurar(p, reg, irmaos_janela)
    evidencias = (_evidenciar(p, reg, irmaos_todos)
                  + _evidencia_divida(divida, escopo_divida)
                  + _evidencia_notificacao(notificacoes or [], p.dt_auto)
                  + _evidencia_termo(termos or [], reg)
                  + _evidencia_uc(uc)
                  + _evidencia_autorizacao(autorizacoes or [], p))
    # O DESFECHO NÃO É EVIDÊNCIA DO PROTOCOLO — VAI SEPARADO, DE PROPÓSITO.
    #
    # O julgamento não responde item nenhum: ele diz se ainda existe caso. Auto
    # já quitado não tem defesa a fazer, e oferecer uma é constrangimento na
    # frente do prospecto. Por isso sai como `situacao_do_auto`, num campo
    # próprio que a tela pode exibir como aviso antes de qualquer análise, em
    # vez de virar mais uma linha no meio das evidências.
    situacao = None
    if julgamento is not None:
        st = (getattr(julgamento, "status_debito", "") or "").strip()
        quitado = "quitado" in st.lower() or "homologado" in st.lower()
        situacao = {
            "status_debito": st or None,
            "decisao": getattr(julgamento, "decisao", None),
            "data_julgamento": (getattr(julgamento, "dat_julg_principal", None)
                                or getattr(julgamento, "dat_julg_recurso", None)),
            "valor_do_auto": getattr(julgamento, "valor_auto", None),
            "valor_pago": getattr(julgamento, "valor_pago", None),
            "moeda": getattr(julgamento, "moeda", None),
            "encerrado": quitado,
            "aviso": (
                "ATENÇÃO: o registro do IBAMA indica que este débito JÁ FOI QUITADO. "
                "Não há defesa a oferecer, e abordar o autuado sobre esta multa seria "
                "erro de carteira. Confira antes de qualquer contato."
                if quitado else
                "O auto consta como julgado no registro do IBAMA. Confira o andamento "
                "antes de dimensionar prazo — o cadastro não substitui o processo."
            ),
            "fonte": "IBAMA — Julgamentos de Auto de Infração (SICAFI)",
        }

    return {
        "num_auto": p.num_auto,
        "apurados": apurados,
        "evidencias": evidencias,
        "situacao_do_auto": situacao,
        "cobertura": {
            "itens_apurados": len(apurados),
            "itens_com_evidencia": len({e["item"] for e in evidencias}),
            "itens_no_protocolo": 60,
        },
        "registro_disponivel": bool(reg),
        "fonte": "IBAMA — Dados Abertos, Fiscalização/Auto de Infração",
        "aviso": (
            "Apuração feita sobre o CADASTRO ADMINISTRATIVO do auto, não sobre o auto "
            "nem sobre o processo. Campo vazio no cadastro não prova peça ausente no "
            "processo. Os itens marcados como apurados resultam de conta sobre dado "
            "presente; todos os demais permanecem com quem analisa."
        ),
    }
