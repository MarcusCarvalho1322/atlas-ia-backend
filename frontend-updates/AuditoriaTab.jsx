// SUBSTITUIR src/components/AuditoriaTab.jsx por este arquivo.
//
// Lê o resultado novo da auditoria (55 itens em 8 módulos) vindo do backend:
// score por módulo, falhas ordenadas por peso, e as teses acionáveis já
// sem repetição — cada tese aparece uma vez, listando quais itens de
// verificação a sustentam.
//
// Onde as duas fontes do acervo divergem sobre a taxa de êxito, a tela mostra
// a divergência em vez de escondê-la atrás de um número único.
import { useState } from 'react'
import { API_BASE, authHeaders } from '../config'

function GeoCard({ formData, casoId, showToast }) {
    const [loading, setLoading] = useState(false)
    const [resultado, setResultado] = useState(null)
    const temCoord = formData.latitude !== '' && formData.longitude !== '' &&
        !isNaN(Number(formData.latitude)) && !isNaN(Number(formData.longitude))

    const verificar = async () => {
        setLoading(true); setResultado(null)
        try {
            const res = await fetch(`${API_BASE}/api/geo/verificar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...authHeaders() },
                body: JSON.stringify({
                    lat: Number(formData.latitude), lon: Number(formData.longitude),
                    bioma: formData.bioma, dataFato: formData.dataFato || null, casoId: casoId || null,
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
            {!temCoord ? (
                <div className="section-sub">Preencha Latitude e Longitude na aba INTAKE para cruzar o caso contra os alertas oficiais de desmatamento do INPE.</div>
            ) : (
                <>
                    <button className="btn btn-outline btn-sm" onClick={verificar} disabled={loading}>
                        {loading ? '⏳ Consultando INPE...' : '🛰️ Verificar coordenada por satélite'}
                    </button>
                    {resultado && (
                        <div style={{ marginTop: 16 }}>
                            <div style={{ fontSize: 13, marginBottom: 10 }}>
                                <strong>{resultado.total_alertas}</strong> alerta(s) oficial(is) num raio de ~{Math.round(resultado.raio_graus * 111)} km da coordenada.
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
                                        {a.area_km2 != null && <span className="badge badge-gold">{a.area_km2.toFixed(3)} km²</span>}
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
            <div className="section-sub">Preencha as verificações na aba INTAKE e execute a auditoria.</div>
            <button className="btn btn-gold" onClick={() => setActiveTab('intake')}>📥 Ir para INTAKE</button>
        </div>
    )

    // Formato antigo (casos salvos antes da integração dos 55 itens)
    const formatoAntigo = !auditResult.teses_acionaveis && auditResult.nulidades
    const { score, resumo, por_modulo, falhas = [], teses_acionaveis = [] } = auditResult
    const scoreColor = score >= 60 ? 'var(--success)' : score >= 30 ? 'var(--gold)' : 'var(--danger)'

    return (
        <div>
            <div className="section-title">🔬 Auditoria Jurídica</div>
            <div className="section-sub">
                {formatoAntigo
                    ? 'Resultado gerado no catálogo anterior de 20 itens. Refaça as verificações na aba INTAKE para usar os 55 itens.'
                    : `Análise determinística sobre ${auditResult.itens_no_catalogo} itens do catálogo, em 8 módulos.`}
            </div>

            {formatoAntigo && (
                <div className="alert-box warning">
                    <div className="alert-title">⚠ RESULTADO EM FORMATO ANTIGO</div>
                    <div className="alert-content">Este caso foi auditado com o catálogo de 20 itens. O catálogo atual tem 55 — reabra a aba INTAKE e refaça as verificações para o diagnóstico completo.</div>
                </div>
            )}

            <div className="grid-2">
                <div className="score-panel">
                    <div className="score-number" style={{ color: scoreColor }}>{score}</div>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, letterSpacing: 2, color: 'var(--text2)', textTransform: 'uppercase', margin: '8px 0' }}>Score de Potencial Defensivo</div>
                    <div className="score-bar"><div className="score-bar-fill" style={{ width: `${score}%`, background: scoreColor }} /></div>
                    <div style={{ fontSize: 13, color: scoreColor, fontWeight: 600 }}>{auditResult.nivel}</div>

                    {!formatoAntigo && (
                        <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 10, lineHeight: 1.7 }}>
                            Sobre o que foi avaliado: <strong>{score}/100</strong> ({auditResult.peso_falha} de {auditResult.peso_avaliado} pontos)<br />
                            Sobre o catálogo inteiro: <strong>{auditResult.score_absoluto}/100</strong> ({auditResult.peso_falha} de {auditResult.pontuacao_maxima} pontos)<br />
                            <span style={{ opacity: .8 }}>As duas leituras só coincidem quando os 55 itens estão respondidos.</span>
                        </div>
                    )}

                    {resumo && (
                        <div className="score-stats">
                            <div className="score-stat"><div className="score-stat-num" style={{ color: 'var(--success)' }}>{resumo.conformes}</div><div className="score-stat-label">Conformes</div></div>
                            <div className="score-stat"><div className="score-stat-num" style={{ color: 'var(--danger)' }}>{resumo.falhas}</div><div className="score-stat-label">Falhas</div></div>
                            <div className="score-stat"><div className="score-stat-num" style={{ color: 'var(--gold)' }}>{resumo.na}</div><div className="score-stat-label">N/A</div></div>
                        </div>
                    )}
                </div>

                <div>
                    <div className="card" style={{ borderColor: 'var(--danger)' }}>
                        <div className="card-title" style={{ color: 'var(--danger)' }}>⚡ Resumo dos Alertas</div>
                        {resumo && (
                            <div style={{ fontSize: 13, color: 'var(--text2)', lineHeight: 2 }}>
                                <div>🔴 <strong style={{ color: 'var(--danger)' }}>{resumo.criticas}</strong> falhas críticas</div>
                                <div>🟠 <strong style={{ color: 'var(--warning)' }}>{resumo.altas}</strong> falhas de risco alto</div>
                                <div>🟡 <strong style={{ color: 'var(--gold)' }}>{resumo.medias}</strong> falhas de risco médio</div>
                                <div>⚖️ <strong style={{ color: 'var(--gold)' }}>{teses_acionaveis.length}</strong> teses acionáveis</div>
                            </div>
                        )}
                        {formData.valorMulta && (
                            <div style={{ marginTop: 12, padding: '8px 12px', background: 'var(--bg3)', borderRadius: 4, fontSize: 13 }}>
                                💰 Multa em análise: <strong style={{ color: 'var(--gold)' }}>R$ {Number(formData.valorMulta).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</strong>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* SCORE POR MÓDULO */}
            {por_modulo && (
                <div className="mt-24">
                    <div className="card-title">📊 Desempenho por Módulo</div>
                    {Object.entries(por_modulo).map(([id, m]) => (
                        <div key={id} style={{ marginBottom: 10 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 4 }}>
                                <span><strong style={{ fontFamily: "'JetBrains Mono', monospace" }}>{id}</strong> {m.titulo}</span>
                                <span style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text2)' }}>
                                    {m.score === null ? 'não avaliado' : `${m.score}% · ${m.falhas} falha(s) de ${m.falhas + m.conformes}`}
                                </span>
                            </div>
                            <div className="score-bar" style={{ height: 6 }}>
                                <div className="score-bar-fill" style={{ width: `${m.score || 0}%`, background: (m.score || 0) >= 60 ? 'var(--danger)' : (m.score || 0) >= 30 ? 'var(--warning)' : 'var(--success)' }} />
                            </div>
                        </div>
                    ))}
                    <div className="section-sub" style={{ marginTop: 6 }}>Barra cheia significa mais falhas encontradas naquele módulo — ou seja, mais material de defesa.</div>
                </div>
            )}

            {/* TESES ACIONÁVEIS */}
            {teses_acionaveis.length > 0 && (
                <div className="mt-24">
                    <div className="card-title">⚖️ Teses Acionáveis — ordenadas pela taxa de êxito registrada</div>
                    {teses_acionaveis.map(t => (
                        <div key={t.id} className="nulidade-card">
                            <div className="nulidade-title">{t.nome}</div>
                            <div className="nulidade-tese">{t.fundamento}</div>
                            <div className="nulidade-meta">
                                <span className="badge badge-gold">Êxito registrado: {t.taxa}%</span>
                                {t.taxa_divergente != null && <span className="badge badge-warning">Outra fonte: {t.taxa_divergente}%</span>}
                                <span className="badge badge-info">
                                    Sustentada por: {t.itens_que_sustentam.map(i => i.id).join(', ')}
                                </span>
                            </div>
                            {t.nota_divergencia && (
                                <div style={{ fontSize: 11.5, color: 'var(--warning)', marginTop: 6 }}>⚠ {t.nota_divergencia}</div>
                            )}
                        </div>
                    ))}
                    <div className="section-sub" style={{ marginTop: 8 }}>
                        As taxas vêm do acervo ATLAS FORENSE e do ATLAS-IA. São indicativas, não garantia de resultado — e onde as duas fontes divergem, ambos os valores estão à vista.
                    </div>
                </div>
            )}

            {/* FALHAS DETALHADAS */}
            {falhas.length > 0 && (
                <div className="mt-24">
                    <div className="card-title">⚠️ Falhas Identificadas — ordenadas por peso</div>
                    {falhas.map(f => (
                        <div key={f.id} className="nulidade-card">
                            <div className="nulidade-title">
                                <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{f.id}</span> — {f.titulo}
                            </div>
                            {f.nota_risco && <div className="nulidade-tese">{f.nota_risco}</div>}
                            {f.acao && <div style={{ fontSize: 12.5, color: 'var(--text2)', marginTop: 4 }}>{f.acao}</div>}
                            <div className="nulidade-meta">
                                <span className={`badge badge-${f.risco === 'CRITICO' ? 'danger' : f.risco === 'ALTO' ? 'warning' : 'gold'}`}>{f.risco}</span>
                                <span className="badge badge-gold">Peso: {f.peso}</span>
                                <span className="badge badge-info">Módulo {f.modulo}</span>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {auditResult.metodologia && (
                <div className="section-sub" style={{ marginTop: 16, fontSize: 11.5 }}>
                    <strong>Metodologia:</strong> {auditResult.metodologia}
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
