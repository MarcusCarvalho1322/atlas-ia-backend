"""
Rotina diária de mineração.

O IBAMA republica a base de autos de infração todo dia. Esta rotina baixa a
versão do dia, compara com o que já está acompanhado e produz um boletim com
o que efetivamente mudou — não uma releitura da mesma lista.

Três perguntas que o boletim responde:
  1. O que APARECEU hoje e não existia ontem?
  2. O que está com PRAZO vencendo nos próximos dias?
  3. O que mudou de valor ou de data no registro público?

O status comercial de cada caso (novo/selecionado/contatado/descartado/cliente)
é preservado entre execuções: a rotina nunca sobrescreve uma decisão humana.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

import prospeccao
from models import Prospecto

# Casos com prazo de defesa apertado entram no boletim de urgência.
LIMIAR_URGENCIA_DIAS = 5

# Campos do registro público que, se mudarem, merecem reaviso.
CAMPOS_MONITORADOS = ("valor", "dt_ciencia", "dt_fato", "processo")


def _aplicar(p: Prospecto, c: prospeccao.Caso) -> list[str]:
    """Atualiza o prospecto com o registro público novo. Devolve o que mudou."""
    novos = {
        "processo": c.processo, "valor": c.valor, "uf": c.uf, "municipio": c.municipio,
        "bioma": c.bioma, "tipo_infracao": c.tipo_infracao, "tipo_pessoa": c.tipo_pessoa,
        "documento_mascarado": c.documento_mascarado, "nome": c.nome,
        "dt_fato": c.dt_fato.isoformat() if c.dt_fato else None,
        "dt_auto": c.dt_auto.isoformat() if c.dt_auto else None,
        "dt_ciencia": c.dt_ciencia.isoformat() if c.dt_ciencia else None,
        "lat": c.lat, "lon": c.lon,
        "sinais": [s.__dict__ for s in c.sinais],
        "prioridade": c.prioridade, "dias_para_defesa": c.dias_para_defesa,
    }
    mudancas = [k for k in CAMPOS_MONITORADOS if getattr(p, k) != novos.get(k)]
    for k, v in novos.items():
        setattr(p, k, v)
    return mudancas


def sincronizar(db: Session, ano: int | None = None, baixar: bool = True,
                pasta: str | Path = "./dados_ibama") -> dict:
    """
    Executa a rotina do dia: baixa a base, ingere, e concilia com o acompanhado.
    O status comercial de cada caso é preservado.
    """
    ano = ano or date.today().year
    pasta = Path(pasta)
    arquivo = pasta / f"auto_infracao_{ano}.csv"

    if baixar:
        prospeccao.baixar_base(pasta, [ano])
    if not arquivo.exists():
        raise FileNotFoundError(f"Base de {ano} não encontrada em {arquivo}.")

    casos = prospeccao.ingerir(arquivo)
    existentes = {p.num_auto: p for p in db.query(Prospecto).all()}

    novos, alterados = [], []
    agora = datetime.now(timezone.utc)

    for c in casos:
        if not c.num_auto:
            continue
        p = existentes.get(c.num_auto)
        if p is None:
            p = Prospecto(num_auto=c.num_auto, status="novo", visto_em=agora)
            _aplicar(p, c)
            db.add(p)
            novos.append(c)
        else:
            mudou = _aplicar(p, c)
            if mudou:
                alterados.append({"num_auto": c.num_auto, "campos": mudou})

    db.commit()
    return {
        "executado_em": agora.isoformat(),
        "ano": ano,
        "casos_na_base": len(casos),
        "novos": len(novos),
        "alterados": len(alterados),
        "detalhe_alterados": alterados[:50],
        "fonte": prospeccao.FONTE,
    }


def boletim(db: Session, limiar_urgencia: int = LIMIAR_URGENCIA_DIAS,
            topo: int = 20, revelar_documento: bool = False) -> dict:
    """
    O que a equipe precisa ver hoje. Só casos ainda não descartados e que não
    viraram cliente — quem já foi tratado sai do radar sozinho.
    """
    hoje = date.today()
    ativos = (db.query(Prospecto)
                .filter(~Prospecto.status.in_(["descartado", "cliente"]))
                .all())

    def _rec(p):
        return p.to_dict(revelar_documento=revelar_documento)

    urgentes = [p for p in ativos
                if p.dias_para_defesa is not None and 0 <= p.dias_para_defesa <= limiar_urgencia]
    urgentes.sort(key=lambda p: (p.dias_para_defesa, -(p.valor or 0)))

    novos = [p for p in ativos if p.status == "novo" and p.visto_em
             and p.visto_em.date() == hoje]
    novos.sort(key=lambda p: -p.prioridade)

    def com_sinal(cod):
        return [p for p in ativos if any(s.get("codigo") == cod for s in (p.sinais or []))]

    decurso = sorted(com_sinal("DECURSO_FATO_AUTO"), key=lambda p: -(p.valor or 0))
    inversao = sorted(com_sinal("INVERSAO_TEMPORAL"), key=lambda p: -(p.valor or 0))

    return {
        "data": hoje.isoformat(),
        "carteira_ativa": len(ativos),
        "valor_em_acompanhamento": round(sum(p.valor or 0 for p in ativos), 2),
        "urgencia": {
            "titulo": f"Prazo de defesa vencendo em até {limiar_urgencia} dias",
            "total": len(urgentes),
            "valor": round(sum(p.valor or 0 for p in urgentes), 2),
            "casos": [_rec(p) for p in urgentes[:topo]],
        },
        "novos_hoje": {
            "titulo": "Autos que apareceram na base hoje",
            "total": len(novos),
            "valor": round(sum(p.valor or 0 for p in novos), 2),
            "casos": [_rec(p) for p in novos[:topo]],
        },
        "decurso_superior_a_3_anos": {
            "titulo": "Mais de 3 anos entre o fato e a lavratura",
            "total": len(decurso),
            "valor": round(sum(p.valor or 0 for p in decurso), 2),
            "casos": [_rec(p) for p in decurso[:topo]],
        },
        "inversao_temporal": {
            "titulo": "Auto lavrado antes da data do fato registrada",
            "total": len(inversao),
            "valor": round(sum(p.valor or 0 for p in inversao), 2),
            "casos": [_rec(p) for p in inversao[:topo]],
        },
        "por_status": {
            s: sum(1 for p in db.query(Prospecto).all() if p.status == s)
            for s in ("novo", "selecionado", "contatado", "descartado", "cliente")
        },
        "fonte": prospeccao.FONTE,
        "aviso": ("Sinais aritméticos apurados sobre o registro público do IBAMA. "
                  "Não constituem qualificação jurídica nem avaliação de mérito."),
    }


# ─────────────────────────────────────────────────────────────────────────
# Agendamento embutido.
#
# Roda dentro do próprio serviço, sem depender de cron externo nem de
# biblioteca extra: acorda todo dia no horário configurado, executa a rotina
# e guarda o boletim. Se a execução falhar, registra e tenta de novo no dia
# seguinte — nunca derruba o serviço.
#
# Configuração: ROTINA_DIARIA_HORA (0-23, horário UTC). Vazio = desligado.
# ─────────────────────────────────────────────────────────────────────────
import asyncio, logging, os

log = logging.getLogger("atlas.rotina")
ultima_execucao: dict = {"quando": None, "resultado": None, "erro": None}


def _segundos_ate(hora_utc: int) -> float:
    from datetime import timedelta
    agora = datetime.now(timezone.utc)
    alvo = agora.replace(hour=hora_utc, minute=0, second=0, microsecond=0)
    if alvo <= agora:
        alvo += timedelta(days=1)
    return (alvo - agora).total_seconds()


async def agendador(session_factory, pasta: str | Path = "./dados_ibama"):
    hora = os.getenv("ROTINA_DIARIA_HORA", "").strip()
    if not hora.isdigit() or not (0 <= int(hora) <= 23):
        log.info("Rotina diária desligada (defina ROTINA_DIARIA_HORA de 0 a 23, em UTC).")
        return
    hora = int(hora)
    log.info("Rotina diária agendada para %02d:00 UTC.", hora)

    while True:
        await asyncio.sleep(_segundos_ate(hora))
        db = session_factory()
        try:
            r = await asyncio.to_thread(sincronizar, db, None, True, pasta)
            b = await asyncio.to_thread(boletim, db)
            ultima_execucao.update({
                "quando": datetime.now(timezone.utc).isoformat(),
                "resultado": {
                    "novos": r["novos"], "alterados": r["alterados"],
                    "casos_na_base": r["casos_na_base"],
                    "urgentes": b["urgencia"]["total"],
                    "valor_urgente": b["urgencia"]["valor"],
                },
                "erro": None,
            })
            log.info("Rotina concluída: %s novos, %s urgentes.", r["novos"], b["urgencia"]["total"])
        except Exception as e:          # nunca derruba o serviço
            ultima_execucao.update({
                "quando": datetime.now(timezone.utc).isoformat(),
                "resultado": None, "erro": str(e),
            })
            log.exception("Rotina diária falhou: %s", e)
        finally:
            db.close()
