"""
Motor de IA do ATLAS-IA — versão servidor.

Isto substitui o que hoje acontece dentro de EstrategiaTab.jsx e
PecasTab.jsx: o navegador do usuário chamava https://api.anthropic.com
diretamente e pedia a chave de API numa janela `prompt()`. Aqui a chave
fica só no servidor (variável de ambiente ANTHROPIC_API_KEY do Railway) e
o front-end passa a chamar este backend, sem nunca ver a chave.

Os textos de system prompt e as regras de cada peça são copiados
literalmente do código React já existente — nenhuma tese jurídica nova foi
adicionada aqui, só o encanamento mudou de lugar.
"""
import os
from anthropic import Anthropic

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("ATLAS_ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY não configurada no servidor.")
        _client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


# ── Idêntico ao SYSTEM_PROMPT de EstrategiaTab.jsx ──────────────────────────
SYSTEM_PROMPT_DIAGNOSTICO = """Você é o ATLAS-IA, sistema especializado em defesa jurídica de autuados em processos de infração ambiental federal no Brasil.
IDENTIDADE: Painel de três especialistas: (1) Advogado sênior 20+ anos em direito ambiental, (2) Engenheiro ambiental expert em DETER/PRODES, (3) Analista de jurisprudência com 1.200+ acórdãos.
BASE LEGAL: Lei 9.605/98, Dec. 6.514/08, LC 140/2011, Lei 9.784/99, Lei 6.830/80, Lei 12.651/12.
JURISPRUDÊNCIA: STF RE 669.069/MG Tema 606, SV 21, STJ REsp 1.251.697/PR, STJ REsp 1.342.071/RJ, STJ REsp 1.340.553/MG, STJ Súmula 393, TRF1 AC 0014232-18.2012.
REGRAS: Nunca cite acórdãos fora desta lista. Nunca invente fatos. Sempre atribua grau de certeza. Sinalize dados ausentes. Use linguagem formal jurídica."""

# ── Idêntico ao SYS de PecasTab.jsx ─────────────────────────────────────────
SYSTEM_PROMPT_PECA = """Você é o ATLAS-IA, sistema especializado em defesa jurídica ambiental federal no Brasil. Redija peças jurídicas formais, completas, com linguagem técnica. Base legal: Lei 9.605/98, Dec. 6.514/08, LC 140/2011, Lei 9.784/99. Jurisprudência: STJ REsp 1.251.697/PR, STJ REsp 1.342.071/RJ, STF Tema 606, SV 21, STJ Súmula 393. Nunca invente fatos. Marque dados ausentes como [COMPLETAR: descrição]. Mínimo 1.500 palavras."""

PECAS_PROMPTS = {
    1: "Redija DEFESA ADMINISTRATIVA DE 1ª INSTÂNCIA completa com: I-Qualificação, II-Preliminares Processuais, III-Mérito Desconstrução Fática, IV-Mérito Desconstrução Jurídica, V-Requerimentos. Mínimo 1.500 palavras.",
    2: "Redija RECURSO ADMINISTRATIVO para a JARI com: I-Admissibilidade, II-Decisão Recorrida, III-Razões do Recurso, IV-Efeito Suspensivo, V-Pedidos. Mínimo 1.200 palavras.",
    3: "Redija RECURSO AO GABIN com enfoque em teses jurídicas e precedentes STJ/STF não apreciados pela JARI. Mínimo 1.000 palavras.",
    4: "Redija MANDADO DE SEGURANÇA COM LIMINAR com: I-Autoridade Coatora, II-Ato Impugnado, III-Direito Líquido e Certo, IV-Fumus/Periculum, V-Pedido de Liminar, VI-Pedido Final. Mínimo 1.000 palavras.",
    5: "Redija EXCEÇÃO DE PRÉ-EXECUTIVIDADE (Súmula 393 STJ) com: I-Cabimento, II-Prescrição, III-Nulidades da CDA, IV-Ilegitimidade, V-Pedido. Mínimo 900 palavras.",
    6: "Redija EMBARGOS À EXECUÇÃO FISCAL com: I-Tempestividade, II-Invalidade do PA, III-Prescrição, IV-Nulidade CDA, V-Excesso de Execução, VI-Inconstitucionalidade, VII-Pedidos. Mínimo 1.500 palavras.",
    7: "Redija PROPOSTA DE TAC/ANPP com: I-Identificação, II-Reconhecimento e Proposta, III-Obrigações de Fazer, IV-Obrigações de Não Fazer, V-Extinção Punibilidade, VI-Suspensão do PA. Mínimo 800 palavras.",
}


def _nulidades_texto(audit: dict | None) -> str:
    """
    Monta o bloco de nulidades para o prompt a partir do resultado da
    auditoria. Aceita o formato novo (55 itens: chaves `falhas` e
    `teses_acionaveis`) e o antigo (20 itens: chave `nulidades`), para que
    casos já salvos continuem gerando peça sem precisar ser reauditados.
    """
    audit = audit or {}

    if audit.get("falhas") or audit.get("teses_acionaveis"):
        linhas = []
        for t in audit.get("teses_acionaveis", []):
            sustentam = ", ".join(i["id"] for i in t.get("itens_que_sustentam", []))
            div = ""
            if t.get("taxa_divergente") is not None:
                div = (f" [ATENÇÃO: as fontes divergem — a outra registra "
                       f"{t['taxa_divergente']}%; tratar a taxa como indicativa]")
            linhas.append(
                f"- {t['nome']} — êxito registrado {t['taxa']}%{div}\n"
                f"    Fundamento: {t.get('fundamento','')}\n"
                f"    Sustentada pelos itens: {sustentam or '—'}"
            )
        achados = [f"- [{f['risco']}] {f['id']} {f['titulo']}"
                   for f in audit.get("falhas", []) if not f.get("teses")]
        if achados:
            linhas.append("\nFalhas sem tese de nulidade associada (instrução do caso):")
            linhas += achados
        return "\n".join(linhas) or "Nenhuma falha registrada na auditoria"

    antigas = audit.get("nulidades") or []
    if not antigas:
        return "Nenhuma nulidade identificada"
    return "\n".join(f"- {n.get('name')} (Peso: {n.get('peso')}, Risco: {n.get('risco')})"
                     for n in antigas)


def gerar_diagnostico(form_data: dict, audit_result: dict | None) -> str:
    user_prompt = f"""Com base nos dados do processo e resultado da auditoria abaixo, gere um DIAGNÓSTICO ESTRATÉGICO COMPLETO.

DADOS DO PROCESSO:
- AIA: {form_data.get('aiaNumero') or '[não informado]'}
- Autuado: {form_data.get('nomeAuituado') or '[não informado]'}
- Infração: {form_data.get('tipoInfracao')}
- Valor Multa: R$ {form_data.get('valorMulta') or '0'}
- Fase: {form_data.get('fase')}
- Bioma: {form_data.get('bioma')}
- Área: {form_data.get('areaHa') or '?'} ha
- Data do fato: {form_data.get('dataFato') or '?'}
- Data AIA: {form_data.get('dataLavratura') or '?'}

NULIDADES IDENTIFICADAS:
{_nulidades_texto(audit_result)}

SCORE: {(audit_result or {}).get('score', 0)}/100

GERE COM ESTAS 6 SEÇÕES:
## 🎯 VEREDITO ESTRATÉGICO
## ⚡ TOP 5 NULIDADES — ORDENADAS POR IMPACTO
## 📋 ESTRATÉGIA DOMINANTE RECOMENDADA
## 💰 ANÁLISE DE CUSTO-BENEFÍCIO
## ⚠️ RISCOS E PONTOS DE ATENÇÃO
## 📊 PROJEÇÃO DE DESFECHO"""

    resp = _get_client().messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT_DIAGNOSTICO,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(b.text for b in resp.content if hasattr(b, "text"))


def gerar_peca(peca_id: int, form_data: dict, audit_result: dict | None) -> str:
    if peca_id not in PECAS_PROMPTS:
        peca_id = 1
    nuls_txt = _nulidades_texto(audit_result)

    dados = (
        f"AIA: {form_data.get('aiaNumero') or '?'}, Autuado: {form_data.get('nomeAuituado') or '?'}, "
        f"CPF/CNPJ: {form_data.get('cpfCnpj') or '?'}, Multa: R$ {form_data.get('valorMulta') or '?'}, "
        f"Infração: {form_data.get('tipoInfracao')}, Artigo: {form_data.get('artigo6514') or '?'}, "
        f"Fase: {form_data.get('fase')}, Bioma: {form_data.get('bioma')}, Área: {form_data.get('areaHa') or '?'} ha"
    )
    base = f"DADOS: {dados}\nNULIDADES:\n{nuls_txt}\nSCORE: {(audit_result or {}).get('score', 0)}/100\n\n"
    user_prompt = base + PECAS_PROMPTS[peca_id]

    resp = _get_client().messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT_PECA,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(b.text for b in resp.content if hasattr(b, "text"))
