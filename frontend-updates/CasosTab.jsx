// SUBSTITUIR src/components/CasosTab.jsx por este arquivo.
//
// O que mudou: os casos agora vêm do backend (GET /api/casos), não mais do
// localStorage — por isso o dashboard funciona igual em qualquer computador
// ou navegador, não só naquele onde o caso foi salvo.
import { useState, useEffect, useCallback } from 'react'
import { API_BASE, authHeaders } from '../config'

export default function CasosTab({ carregarCaso, showToast }) {
    const [casos, setCasos] = useState([])
    const [carregando, setCarregando] = useState(true)
    const [filtroFase, setFiltroFase] = useState('')

    const buscarCasos = useCallback(async () => {
        setCarregando(true)
        try {
            const res = await fetch(`${API_BASE}/api/casos`, { headers: authHeaders() })
            if (!res.ok) throw new Error(`HTTP ${res.status}`)
            setCasos(await res.json())
        } catch (e) {
            showToast(`Não foi possível carregar os casos: ${e.message}`, 'danger')
        }
        setCarregando(false)
    }, [showToast])

    useEffect(() => { buscarCasos() }, [buscarCasos])

    const excluir = async (id) => {
        if (!window.confirm('Excluir este caso permanentemente?')) return
        try {
            const res = await fetch(`${API_BASE}/api/casos/${id}`, { method: 'DELETE', headers: authHeaders() })
            if (!res.ok) throw new Error(`HTTP ${res.status}`)
            setCasos(prev => prev.filter(c => c.id !== id))
            showToast('Caso excluído', 'danger')
        } catch (e) {
            showToast(`Não foi possível excluir: ${e.message}`, 'danger')
        }
    }

    const totalMultas = casos.reduce((s, c) => s + (parseFloat(c.formData?.valorMulta) || 0), 0)
    const filtered = filtroFase ? casos.filter(c => c.formData?.fase?.includes(filtroFase)) : casos

    const calcUrgencia = (caso) => {
        if (!caso.formData?.dataNotificacao) return 999
        const prazo = new Date(caso.formData.dataNotificacao)
        prazo.setDate(prazo.getDate() + 20)
        return Math.ceil((prazo - new Date()) / 86400000)
    }

    const sorted = [...filtered].sort((a, b) => calcUrgencia(a) - calcUrgencia(b))

    return (
        <div>
            <div className="section-title">💼 Dashboard de Casos</div>
            <div className="section-sub">Gestão de todos os processos salvos — agora em nuvem, acessível de qualquer computador</div>

            <div className="flex-between" style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 14 }}>
                    <strong style={{ color: 'var(--gold)' }}>{casos.length}</strong> casos ativos — <strong style={{ color: 'var(--gold)' }}>R$ {totalMultas.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</strong> em multas gerenciadas
                </div>
                <select className="form-select" style={{ width: 'auto', fontSize: 12 }} value={filtroFase} onChange={e => setFiltroFase(e.target.value)}>
                    <option value="">Todas as fases</option>
                    <option value="1ª">Defesa 1ª Instância</option>
                    <option value="JARI">Recurso JARI</option>
                    <option value="GABIN">Recurso GABIN</option>
                    <option value="Dívida">Dívida Ativa</option>
                    <option value="Execução">Execução Fiscal</option>
                </select>
            </div>

            {carregando ? (
                <div className="spinner-wrap"><div className="spinner" /><div className="spinner-text">Carregando casos...</div></div>
            ) : sorted.length === 0 ? (
                <div className="alert-box info">
                    <div className="alert-title">📂 NENHUM CASO SALVO</div>
                    <div className="alert-content">Preencha um processo na aba INTAKE e clique em "Salvar Caso" no cabeçalho para começar a monitorar.</div>
                </div>
            ) : (
                sorted.map(caso => {
                    const dias = calcUrgencia(caso)
                    const isUrgent = dias <= 5 && dias > -999
                    return (
                        <div key={caso.id} className={`caso-card ${isUrgent ? 'urgent' : ''}`}>
                            <div className="caso-header">
                                <div>
                                    <div className="caso-aia">{caso.formData?.aiaNumero || 'AIA não informado'} {isUrgent && <span className="badge badge-danger">🚨 URGENTE</span>}</div>
                                    <div className="caso-name">{caso.formData?.nomeAuituado || 'Autuado não informado'}</div>
                                </div>
                                {caso.auditResult && (
                                    <div style={{ textAlign: 'right' }}>
                                        <div style={{ fontFamily: "'Playfair Display', serif", fontSize: 28, fontWeight: 900, color: caso.auditResult.score >= 60 ? 'var(--success)' : caso.auditResult.score >= 30 ? 'var(--gold)' : 'var(--danger)' }}>
                                            {caso.auditResult.score}
                                        </div>
                                        <div className="text-xs text-muted mono">Score</div>
                                    </div>
                                )}
                            </div>
                            <div className="caso-meta">
                                <span>💰 R$ {(parseFloat(caso.formData?.valorMulta) || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
                                <span>📋 {caso.formData?.fase?.split(' ').slice(0, 3).join(' ') || '—'}</span>
                                {dias < 999 && <span style={{ color: dias <= 5 ? 'var(--danger)' : 'var(--success)' }}>⏰ {dias > 0 ? `${dias} dias` : 'Vencido'}</span>}
                                <span>📅 Salvo: {new Date(caso.savedAt).toLocaleDateString('pt-BR')}</span>
                            </div>
                            <div className="caso-actions">
                                <button className="btn btn-gold btn-sm" onClick={() => carregarCaso(caso)}>📂 Carregar</button>
                                <button className="btn btn-danger btn-sm" onClick={() => excluir(caso.id)}>🗑️ Excluir</button>
                            </div>
                        </div>
                    )
                })
            )}
        </div>
    )
}
