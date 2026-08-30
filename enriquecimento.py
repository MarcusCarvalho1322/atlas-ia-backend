"""
Enriquecimento de contato dos casos minerados.

A base do IBAMA identifica o autuado (nome e documento) e o município, mas
**não traz nenhum dado de contato** — não há endereço, telefone ou e-mail em
nenhuma das 84 colunas. O contato precisa vir de outra fonte, e aqui a
distinção entre empresa e pessoa física não é um detalhe: é a linha que separa
o que é legítimo do que não é.

┌─ PESSOA JURÍDICA ─────────────────────────────────────────────────────────┐
│ A Receita Federal publica o Cadastro Nacional da Pessoa Jurídica como dado │
│ aberto: razão social, endereço completo, telefone, situação cadastral e    │
│ CNAE. É registro empresarial público, feito para consulta. Este módulo     │
│ consulta essa base e devolve o contato.                                    │
└───────────────────────────────────────────────────────────────────────────┘

┌─ PESSOA FÍSICA ───────────────────────────────────────────────────────────┐
│ Não existe fonte pública e legítima de telefone ou e-mail a partir de CPF. │
│ Quem vende isso opera sobre bases vazadas ou raspadas — e usar esse tipo   │
│ de origem num negócio cujo produto é rigor forense é risco desproporcional │
│ ao ganho: além da exposição sob a LGPD, é o tipo de coisa que a parte      │
│ contrária usa para desqualificar o trabalho inteiro.                       │
│                                                                            │
│ Por isso este módulo NÃO tenta obter contato de pessoa física. Em vez      │
│ disso, `territorio()` mostra onde os casos se concentram, para que a       │
│ aproximação aconteça por canal local — sindicato rural, cooperativa,       │
│ associação — em vez de contato individual.                                 │
└───────────────────────────────────────────────────────────────────────────┘

Fonte de PJ: Receita Federal · Cadastro Nacional da Pessoa Jurídica,
consultado via BrasilAPI (https://brasilapi.com.br) — a mesma que o
SafraCheck.IA já usa em `src/lib/engines/brasilapi.ts`.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import httpx
from sqlalchemy.orm import Session

from models import Prospecto, CacheConsulta

FONTE_PJ = "Receita Federal · Cadastro Nacional da Pessoa Jurídica (via BrasilAPI)"
FONTE_PJ_URL = "https://brasilapi.com.br/api/cnpj/v1/"
VALIDADE_CACHE_DIAS = 30


def _so_digitos(v: str | None) -> str:
    return "".join(c for c in (v or "") if c.isdigit())


def _telefone(ddd_numero: str | None) -> str | None:
    """A Receita entrega DDD e número colados. Separa para ficar discável."""
    d = _so_digitos(ddd_numero)
    if len(d) < 10:
        return None
    return f"({d[:2]}) {d[2:-4]}-{d[-4:]}"


def _formatar(dados: dict) -> dict:
    endereco = " ".join(x for x in [
        dados.get("descricao_tipo_de_logradouro"), dados.get("logradouro"),
        dados.get("numero"), dados.get("complemento"),
    ] if x)
    return {
        "razao_social": dados.get("razao_social"),
        "nome_fantasia": dados.get("nome_fantasia") or None,
        "situacao_cadastral": dados.get("descricao_situacao_cadastral"),
        "atividade_principal": dados.get("cnae_fiscal_descricao"),
        "endereco": endereco.strip() or None,
        "bairro": dados.get("bairro") or None,
        "municipio": dados.get("municipio"),
        "uf": dados.get("uf"),
        "cep": dados.get("cep"),
        "telefones": [t for t in (_telefone(dados.get("ddd_telefone_1")),
                                  _telefone(dados.get("ddd_telefone_2"))) if t],
        "email": dados.get("email") or None,
    }


def consultar_cnpj(db: Session, cnpj: str, timeout: float = 25.0) -> dict:
    """
    Consulta o cadastro público da empresa. Cache de 30 dias.

    Nunca inventa: se a consulta falhar, devolve `ok: False` com o motivo e
    recomenda a consulta manual — mesmo comportamento das engines do
    SafraCheck, que preferem admitir a lacuna a preencher com suposição.
    """
    chave = _so_digitos(cnpj)
    base = {"cnpj": chave, "fonte": FONTE_PJ, "fonte_url": FONTE_PJ_URL + chave}

    if len(chave) != 14:
        return {**base, "ok": False, "erro": "CNPJ inválido (esperados 14 dígitos)."}

    c = db.query(CacheConsulta).filter(
        CacheConsulta.origem == "receita_cnpj", CacheConsulta.chave == chave).first()
    if c and c.expira_em and c.expira_em > datetime.now(timezone.utc).replace(tzinfo=None):
        return {**base, "ok": True, "consultado_em": c.buscado_em.isoformat(),
                "do_cache": True, **c.resultado}

    try:
        r = httpx.get(FONTE_PJ_URL + chave, timeout=timeout)
        if r.status_code == 404:
            return {**base, "ok": False, "erro": "CNPJ não encontrado no cadastro público."}
        if r.status_code == 429:
            return {**base, "ok": False, "erro": "Limite de consultas atingido; tente novamente em instantes.",
                    "consulta_manual_recomendada": True}
        r.raise_for_status()
        dados = _formatar(r.json())
    except httpx.HTTPError as e:
        return {**base, "ok": False, "erro": f"Cadastro indisponível no momento: {e}",
                "consulta_manual_recomendada": True}

    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    if c:
        c.resultado, c.buscado_em = dados, agora
        c.expira_em = agora + timedelta(days=VALIDADE_CACHE_DIAS)
    else:
        db.add(CacheConsulta(origem="receita_cnpj", chave=chave, resultado=dados,
                             buscado_em=agora,
                             expira_em=agora + timedelta(days=VALIDADE_CACHE_DIAS)))
    db.commit()
    return {**base, "ok": True, "consultado_em": agora.isoformat(), "do_cache": False, **dados}


def contato_do_caso(db: Session, p: Prospecto) -> dict:
    """Resolve o contato de um caso da carteira, conforme o tipo de pessoa."""
    if (p.tipo_pessoa or "").upper() == "PJ":
        if not p.cnpj:
            return {"tipo": "PJ", "disponivel": False,
                    "motivo": "O CNPJ não foi capturado na ingestão deste caso."}
        r = consultar_cnpj(db, p.cnpj)
        return {"tipo": "PJ", "disponivel": bool(r.get("ok")), **r}

    return {
        "tipo": "PF",
        "disponivel": False,
        "motivo": ("Não há fonte pública e legítima de telefone ou e-mail a partir de CPF. "
                   "Este sistema não consulta bases de origem não verificável."),
        "caminho_recomendado": (
            f"Aproximação por canal local em {p.municipio or 'município do auto'}/{p.uf or ''} — "
            "sindicato rural, cooperativa ou associação de produtores. Ver /api/prospeccao/territorio "
            "para onde os casos se concentram."),
        "dados_publicos_disponiveis": {
            "municipio": p.municipio, "uf": p.uf,
            "processo": p.processo, "documento_mascarado": p.documento_mascarado,
        },
    }


def territorio(db: Session, tipo_pessoa: str = "PF", topo: int = 50) -> dict:
    """
    Onde os casos se concentram geograficamente.

    É a resposta operacional para a pessoa física: em vez de perseguir milhares
    de contatos individuais que não existem de forma legítima, mostra os poucos
    municípios que concentram a maior parte do valor — que é onde vale colocar
    parceria local, conteúdo dirigido e presença.
    """
    ativos = (db.query(Prospecto)
                .filter(~Prospecto.status.in_(["descartado", "cliente"]))
                .filter(Prospecto.tipo_pessoa == tipo_pessoa.upper())
                .all())

    agrupado = defaultdict(lambda: {"autos": 0, "valor": 0.0, "urgentes": 0})
    for p in ativos:
        k = f"{(p.municipio or '?').title()}/{p.uf or '?'}"
        g = agrupado[k]
        g["autos"] += 1
        g["valor"] += p.valor or 0
        if p.dias_para_defesa is not None and 0 <= p.dias_para_defesa <= 20:
            g["urgentes"] += 1

    ordenado = sorted(agrupado.items(), key=lambda x: -x[1]["valor"])
    total = sum(v["valor"] for v in agrupado.values())

    linhas, acumulado = [], 0.0
    for i, (mun, g) in enumerate(ordenado[:topo], 1):
        acumulado += g["valor"]
        linhas.append({
            "posicao": i, "municipio": mun, "autos": g["autos"],
            "valor": round(g["valor"], 2), "urgentes": g["urgentes"],
            "acumulado_pct": round(acumulado / total * 100, 1) if total else 0,
        })

    return {
        "tipo_pessoa": tipo_pessoa.upper(),
        "municipios_com_casos": len(agrupado),
        "valor_total": round(total, 2),
        "concentracao": linhas,
        "leitura": (f"Os {len(linhas)} municípios listados concentram "
                    f"{linhas[-1]['acumulado_pct'] if linhas else 0}% do valor. "
                    "Presença nesses pontos alcança a maior parte da carteira sem "
                    "depender de contato individual."),
    }
