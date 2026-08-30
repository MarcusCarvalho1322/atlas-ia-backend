// SUBSTITUIR src/components/AuditoriaTab.jsx por este arquivo.
//
// O que mudou: adicionado um card "Verificação Geoespacial (INPE)" que chama
// o atlas-geo (POST /api/geo/verificar) e cruza a latitude/longitude do RV
// contra as bases oficiais DETER + PRODES. Nada no motor de score original
// (as 20 regras, os pesos, o cálculo) foi alterado.
import { useState } from 'react'
import { API_BASE, authHeaders } from '../config'

function GeoCard({ formData, casoId, showToast }) {
    const [loading, setLoading] = useState(false)
    const [resultado, setResultado] = useState(null)
    const temCoordenadas = formData.latitude !== '' && formData.longitude !== '' && !isNaN(Number(formData.latitude)) && !isNaN(Number(formData.longitude))

    const verificar = async () => {
        setLoading(true); setResultado(null)
        try {
            const res = await fetch(`${API_BASE}/api/geo/verificar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...authHeaders() },
                body: JSON.stringify({
                    lat: Number(formData.latitude),
                    lon: Number(formData.longitude),
                    bioma: formData.bioma,
                    dataFato: formData.dataFato || null,
                    casoId: casoId || null,
                }),
            })
            const data = await res.json()
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
            setResultado(data)
        } catch (e) {
            showToast(`Falha na verificação por satélite: ${e.message}`, 'danger')
        }
        setLoading(false)
    }

    return (
        <div className="card" style={{ marginTop: 24 }}>
            <div className="card-title">🛰️ Verificação Geoespacial — DETER/PRODES (INPE)</div>
            {!temCoordenadas ? (
                <div className="section-sub">Preencha Latitude e Longitude na aba INTAKE (Seção "A Infração") para cruzar o caso contra os alertas oficiais de desmatamento do INPE.</div>
            ) : (
                <>
                    <button className="btn btn-outline btn-sm" onClick={verificar} disabled={loading}>
                        {loading ? '⏳ Consultando INPE...' : '🛰️ Verificar coordenada por satélite'}
                    </button>
                    {resultado && (
                        <div style={{ marginTop: 16 }}>
                            <div style={{ fontSize: 13, marginBottom: 10 }}>
                                <strong>{resultado.total_alertas}</strong> alerta(s) oficial(is) encontrado(s) num raio de ~{Math.round(resultado.raio_graus * 111)} km da coordenada informada.
                            </div>
                            {resultado.nota_compatibilidade_data && (
                                <div className={`alert-box ${resultado.total_alertas > 0 ? 'warning' : 'info'}`} style={{ marginBottom: 12 }}>
                                    <div className="alert-content">{resultado.nota_compatibilidade_data}</div>
                                </div>
                            )}
                            {resultado.alertas.slice(0, 8).map((a, i) => (
                                <div key={i} className="nulidade-card conform" style={{ marginBottom: 8 }}>
                                    <div className="nulidade-title">{a.fonte} · {a.classe}{a.subclasse ? ` (${a.subclasse})` : ''}</div>
                                    <div className="nulidade-meta">
                                        <span className="badge badge-info">{a.data_imagem || a.ano_referencia}</span>
                                        <span className="badge badge-gold">{a.municipio || a.uf}</span>
                                        {a.area_km2 && <span className="badge badge-gold">{a.area_km2.toFixed(3)} km²</span>}
                                        <span className="badge badge-info">{a.satelite}/{a.sensor}</span>
                                    </div>
                                </div>
                            ))}
                            {resultado.avisos?.length > 0 && (
                                <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 8 }}>
                                    {resultado.avisos.map((a, i) => <div key={i}>ℹ️ {a}</div>)}
                                </div>
                            )}
                            <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 10 }}>Fonte: {resultado.fonte}</div>
                        </div>
                    )}
                </>
            )}
        </div>
    )
}

export default function AuditoriaTab({ auditResult, formData, casoId, setActiveTab, showToast }) {
    if (!auditResult) return (
        <div className="spinner-wrap">
            <div style={{ fontSize: 48, marginBottom: 16 }}>🔬</div>
            <div className="section-title" style={{ marginBottom: 8 }}>Aguardando Dados</div>
            <div className="section-sub">Preencha o formulário na aba INTAKE e clique em "Executar Auditoria" para gerar o diagnóstico.</div>
            <button className="btn btn-gold" onClick={() => setActiveTab('intake')}>📥 Ir para INTAKE</button>
        </div>
    )

    const { score, nulidades, conformes, naCount } = auditResult
    const scoreColor = score >= 60 ? 'var(--success)' : score >= 30 ? 'var(--gold)' : 'var(--danger)'
    const nivel = score >= 60 ? '🏆 ALTO POTENCIAL — Múltiplas nulidades' : score >= 30 ? '⚖️ MÉDIO POTENCIAL — Nulidades relevantes' : '⚠️ BAIXO POTENCIAL — Focar em dosimetria e redução'

    return (
        <div>
            <div className="section-title">🔬 Auditoria Jurídica</div>
            <div className="section-sub">Resultado da análise determinística de 20 regras de auditoria</div>

            <div className="grid-2">
                <div className="score-panel">
                    <div className="score-number" style={{ color: scoreColor }}>{score}</div>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, letterSpacing: 2, color: 'var(--text2)', textTransform: 'uppercase', margin: '8px 0' }}>Score de Potencial Defensivo</div>
                    <div className="score-bar"><div className="score-bar-fill" style={{ width: `${score}%`, background: scoreColor }} /></div>
                    <div style={{ fontSize: 13, color: scoreColor, fontWeight: 600 }}>{nivel}</div>
                    <div className="score-stats">
                        <div className="score-stat"><div className="score-stat-num" style={{ color: 'var(--success)' }}>{conformes.length}</div><div className="score-stat-label">Conformes</div></div>
                        <div className="score-stat"><div className="score-stat-num" style={{ color: 'var(--danger)' }}>{nulidades.length}</div><div className="score-stat-label">Falhas</div></div>
                        <div className="score-stat"><div className="score-stat-num" style={{ color: 'var(--gold)' }}>{naCount}</div><div className="score-stat-label">N/A</div></div>
                    </div>
                </div>

                <div>
                    <div className="card" style={{ borderColor: 'var(--danger)' }}>
                        <div className="card-title" style={{ color: 'var(--danger)' }}>⚡ Resumo dos Alertas</div>
                        <div style={{ fontSize: 13, color: 'var(--text2)', lineHeight: 2 }}>
                            <div>🔴 <strong style={{ color: 'var(--danger)' }}>{nulidades.filter(n => n.risco === 'CRÍTICO').length}</strong> nulidades graves</div>
                            <div>🟠 <strong style={{ color: 'var(--warning)' }}>{nulidades.filter(n => n.risco === 'ALTO').length}</strong> fragilidades altas</div>
                            <div>🟡 <strong style={{ color: 'var(--gold)' }}>{nulidades.filter(n => n.risco === 'MÉDIO').length}</strong> fragilidades médias</div>
                            <div>🟢 <strong style={{ color: 'var(--success)' }}>{conformes.length}</strong> itens conformes</div>
                        </div>
                        {formData.valorMulta && <div style={{ marginTop: 12, padding: '8px 12px', background: 'var(--bg3)', borderRadius: 4, fontSize: 13 }}>
                            💰 Multa em análise: <strong style={{ color: 'var(--gold)' }}>R$ {Number(formData.valorMulta).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</strong>
                        </div>}
                    </div>
                </div>
            </div>

            {/* NULIDADES */}
            <div className="mt-24">
                <div className="card-title">⚠️ Nulidades Identificadas — Ordenadas por Impacto</div>
                {nulidades.map((n, i) => (
                    <div key={i} className="nulidade-card">
                        <div className="nulidade-title">{n.name}</div>
                        <div className="nulidade-tese">{n.tese}</div>
                        <div className="nulidade-meta">
                            <span className={`badge badge-${n.risco === 'CRÍTICO' ? 'danger' : n.risco === 'ALTO' ? 'warning' : 'gold'}`}>{n.risco}</span>
                            <span className="badge badge-info">Êxito: {n.taxa}%</span>
                            <span className="badge badge-gold">Peso: {n.peso}/178</span>
                        </div>
                    </div>
                ))}
            </div>

            {/* CONFORMES */}
            {conformes.length > 0 && (
                <div className="mt-24">
                    <div className="card-title" style={{ color: 'var(--success)' }}>✅ Itens Conformes</div>
                    {conformes.map((c, i) => (
                        <div key={i} className="nulidade-card conform">
                            <div className="nulidade-title" style={{ color: 'var(--success)' }}>{c.name}</div>
                        </div>
                    ))}
                </div>
            )}

            <GeoCard formData={formData} casoId={casoId} showToast={showToast} />

            <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
                <button className="btn btn-gold btn-lg" onClick={() => setActiveTab('estrategia')}>🤖 GERAR DIAGNÓSTICO ESTRATÉGICO IA →</button>
                <button className="btn btn-info btn-lg" onClick={() => setActiveTab('pecas')}>✍️ GERAR PEÇAS DIRETAMENTE →</button>
            </div>
        </div>
    )
}
