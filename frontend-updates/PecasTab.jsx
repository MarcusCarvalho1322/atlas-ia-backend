// SUBSTITUIR src/components/PecasTab.jsx por este arquivo.
//
// Mesma mudança do EstrategiaTab.jsx: a geração passa a chamar o backend
// atlas-geo (POST /api/peca) em vez de pedir a API key ao usuário no navegador.
import { useState } from 'react'
import { API_BASE, authHeaders } from '../config'

const PECAS = [
    { id: 1, icon: '📄', name: 'Defesa Administrativa 1ª Instância', when: 'Prazo de 20 dias da notificação', fase: '1ª Instância' },
    { id: 2, icon: '📑', name: 'Recurso Administrativo (JARI)', when: 'Após decisão de 1ª instância desfavorável', fase: '2ª Instância' },
    { id: 3, icon: '📋', name: 'Recurso ao GABIN (3ª Instância)', when: 'Após decisão da JARI desfavorável', fase: '3ª Instância' },
    { id: 4, icon: '⚖️', name: 'Mandado de Segurança c/ Liminar', when: 'Ilegalidade manifesta', fase: 'Judicial' },
    { id: 5, icon: '🛡️', name: 'Exceção de Pré-Executividade', when: 'Execução fiscal sem garantia do juízo', fase: 'Execução' },
    { id: 6, icon: '📜', name: 'Embargos à Execução Fiscal', when: 'Penhora realizada, 30 dias', fase: 'Execução' },
    { id: 7, icon: '🤝', name: 'Proposta de TAC / ANPP', when: 'Estratégia de desjudicialização', fase: 'Acordo' },
]

export default function PecasTab({ formData, auditResult }) {
    const [selected, setSelected] = useState(null)
    const [output, setOutput] = useState('')
    const [loading, setLoading] = useState(false)
    const [generated, setGenerated] = useState({})

    const gerar = async () => {
        if (!selected) return
        setLoading(true); setOutput('')
        try {
            const res = await fetch(`${API_BASE}/api/peca`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...authHeaders() },
                body: JSON.stringify({ pecaId: selected, formData, auditResult }),
            })
            const data = await res.json()
            const text = data.output || data.detail || 'Erro na geração.'
            setOutput(text)
            setGenerated(prev => ({ ...prev, [selected]: true }))
        } catch (e) {
            setOutput(`⚠️ Não foi possível conectar ao motor de IA (atlas-geo).\n\nErro: ${e.message}`)
        }
        setLoading(false)
    }

    return (
        <div>
            <div className="section-title">✍️ Geração de Peças Jurídicas</div>
            <div className="section-sub">Selecione o tipo de peça e gere automaticamente com base nos dados do processo</div>

            <div className="pecas-grid">
                {PECAS.map(p => (
                    <div key={p.id} className={`peca-card ${selected === p.id ? 'selected' : ''}`} onClick={() => setSelected(p.id)}>
                        <div className="peca-icon">{p.icon}</div>
                        <div className="peca-name">{p.name} {generated[p.id] && <span className="badge badge-success">Gerada</span>}</div>
                        <div className="peca-when">{p.when}</div>
                        <div style={{ marginTop: 6 }}><span className="badge badge-info">{p.fase}</span></div>
                    </div>
                ))}
            </div>

            {selected && (
                <button className="btn btn-gold btn-lg" style={{ width: '100%', justifyContent: 'center', marginTop: 16 }} onClick={gerar} disabled={loading}>
                    {loading ? '⏳ Gerando peça...' : `✍️ GERAR ${PECAS.find(p => p.id === selected)?.name.toUpperCase()}`}
                </button>
            )}

            {loading && <div className="spinner-wrap"><div className="spinner" /><div className="spinner-text">Redigindo peça jurídica...</div></div>}

            {output && (
                <div style={{ marginTop: 24 }}>
                    <div className="output-actions">
                        <button className="btn btn-outline btn-sm" onClick={() => navigator.clipboard.writeText(output)}>📋 Copiar</button>
                        <button className="btn btn-outline btn-sm" onClick={() => { const b = new Blob([output], { type: 'text/plain' }); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = `peca-${selected}-atlas-ia.txt`; a.click() }}>💾 Baixar TXT</button>
                        <button className="btn btn-outline btn-sm" onClick={() => window.print()}>🖨️ Imprimir</button>
                        <button className="btn btn-outline btn-sm" onClick={gerar}>🔄 Regenerar</button>
                    </div>
                    <div className="prompt-output">{output}</div>
                    <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 8, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>
                        {output.length.toLocaleString('pt-BR')} caracteres · ~{(output.length / 2000).toFixed(1)} páginas A4
                    </div>
                    <div className="alert-box warning" style={{ marginTop: 16 }}>
                        <div className="alert-title">⚠ AVISO IMPORTANTE</div>
                        <div className="alert-content">Esta peça foi gerada por IA e deve ser revisada por advogado habilitado antes do protocolo. Campos [COMPLETAR: ...] devem ser preenchidos com dados específicos do caso.</div>
                    </div>
                </div>
            )}
        </div>
    )
}
