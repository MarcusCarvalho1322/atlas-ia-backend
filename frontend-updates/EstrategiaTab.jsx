// SUBSTITUIR src/components/EstrategiaTab.jsx por este arquivo.
//
// O que mudou: em vez de chamar api.anthropic.com direto do navegador e pedir
// a chave via prompt(), agora chama o backend atlas-geo, que guarda a chave
// em segredo. O usuário final não vê mais nenhuma janela pedindo API key.
import { useState } from 'react'
import { API_BASE, authHeaders } from '../config'

const LOADING_MSGS = ['Analisando jurisprudência aplicável...', 'Identificando nulidades...', 'Formulando estratégia...', 'Gerando diagnóstico completo...']

export default function EstrategiaTab({ formData, auditResult }) {
    const [output, setOutput] = useState('')
    const [loading, setLoading] = useState(false)
    const [loadingMsg, setLoadingMsg] = useState('')

    const gerarDiagnostico = async () => {
        setLoading(true); setOutput('')
        let msgIdx = 0
        const interval = setInterval(() => { setLoadingMsg(LOADING_MSGS[msgIdx % LOADING_MSGS.length]); msgIdx++ }, 2000)

        try {
            const res = await fetch(`${API_BASE}/api/diagnostico`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...authHeaders() },
                body: JSON.stringify({ formData, auditResult }),
            })
            const data = await res.json()
            setOutput(data.output || data.detail || 'Erro na geração.')
        } catch (e) {
            setOutput(`⚠️ Não foi possível conectar ao motor de IA (atlas-geo).\n\nErro: ${e.message}\n\nVerifique se o serviço está no ar e se VITE_ATLAS_API_URL está configurado corretamente.`)
        }
        clearInterval(interval); setLoading(false)
    }

    return (
        <div>
            <div className="section-title">📊 Diagnóstico Estratégico — Motor ATLAS-IA</div>
            <div className="section-sub">Análise estratégica completa gerada por inteligência artificial com base nos dados do processo e auditoria</div>

            {!auditResult && (
                <div className="alert-box warning">
                    <div className="alert-title">⚠ AUDITORIA PENDENTE</div>
                    <div className="alert-content">Execute a auditoria na aba INTAKE antes de gerar o diagnóstico estratégico.</div>
                </div>
            )}

            <button className="btn btn-gold btn-lg" onClick={gerarDiagnostico} disabled={loading} style={{ marginBottom: 24 }}>
                {loading ? '⏳ Gerando...' : '🤖 GERAR DIAGNÓSTICO ESTRATÉGICO'}
            </button>

            {loading && (
                <div className="spinner-wrap">
                    <div className="spinner" />
                    <div className="spinner-text">{loadingMsg}</div>
                </div>
            )}

            {output && (
                <div>
                    <div className="output-actions">
                        <button className="btn btn-outline btn-sm" onClick={() => { navigator.clipboard.writeText(output); }}>📋 Copiar</button>
                        <button className="btn btn-outline btn-sm" onClick={() => { const b = new Blob([output], { type: 'text/plain' }); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = 'diagnostico-atlas-ia.txt'; a.click() }}>💾 Baixar TXT</button>
                        <button className="btn btn-outline btn-sm" onClick={gerarDiagnostico}>🔄 Regenerar</button>
                    </div>
                    <div className="prompt-output">{output}</div>
                    <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 8, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>
                        {output.length.toLocaleString('pt-BR')} caracteres · ~{Math.ceil(output.length / 2000)} páginas A4
                    </div>
                </div>
            )}
        </div>
    )
}
