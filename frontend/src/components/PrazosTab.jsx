import { useMemo } from 'react'

function addDays(date, d) { const r = new Date(date); r.setDate(r.getDate() + d); return r }
function addYears(date, y) { const r = new Date(date); r.setFullYear(r.getFullYear() + y); return r }
function fmt(d) { return d ? new Date(d).toLocaleDateString('pt-BR') : '—' }
function diffDays(a, b) { return Math.ceil((new Date(a) - new Date(b)) / 86400000) }

export default function PrazosTab({ formData }) {
    const hoje = new Date()
    const { dataFato, dataLavratura, dataNotificacao, valorMulta } = formData

    const events = useMemo(() => {
        const ev = []
        if (dataFato) ev.push({ date: new Date(dataFato), label: 'Data do Fato', status: 'past', fundamento: 'Ponto de origem do processo', icon: '📌' })
        if (dataLavratura) ev.push({ date: new Date(dataLavratura), label: 'Lavratura do AIA', status: 'past', fundamento: 'Data de emissão do Auto de Infração', icon: '📋' })
        if (dataNotificacao) {
            ev.push({ date: new Date(dataNotificacao), label: 'Notificação', status: 'past', fundamento: 'Data de ciência do autuado', icon: '📬' })
            const prazo = addDays(dataNotificacao, 20)
            const d = diffDays(prazo, hoje)
            ev.push({ date: prazo, label: 'PRAZO DE DEFESA ADMINISTRATIVA', status: d <= 0 ? 'expired' : d <= 5 ? 'current' : 'future', fundamento: 'Notificação + 20 dias úteis', action: d > 0 ? `${d} dias restantes` : 'VENCIDO', icon: '⏰' })
        }
        if (dataFato) {
            const presc = addYears(dataFato, 3)
            const consumada = presc < hoje
            ev.push({ date: presc, label: 'PRESCRIÇÃO PUNITIVA', status: consumada ? 'expired' : 'future', fundamento: 'Art. 21 Dec. 6.514/08 — Fato + 3 anos', action: consumada ? '⚡ CONSUMADA — Arguir imediatamente!' : `Em ${diffDays(presc, hoje)} dias`, icon: consumada ? '⚡' : '📅' })
        }
        if (dataFato) {
            const presc5 = addYears(dataFato, 5)
            ev.push({ date: presc5, label: 'Prazo máximo inscrição em DA', status: presc5 < hoje ? 'expired' : 'future', fundamento: 'Trânsito + 5 anos para inscrição', icon: '📊' })
        }
        if (dataFato) {
            const exec = addYears(dataFato, 8)
            ev.push({ date: exec, label: 'Prescrição executória estimada', status: exec < hoje ? 'expired' : 'future', fundamento: 'Inscrição DA + 5 anos (estimativa)', icon: '⚖️' })
        }
        ev.sort((a, b) => a.date - b.date)
        return ev
    }, [dataFato, dataLavratura, dataNotificacao])

    const valorOriginal = parseFloat(valorMulta) || 0
    const mesesDesde = dataLavratura ? Math.max(0, Math.round(diffDays(hoje, new Date(dataLavratura)) / 30)) : 0
    const selicMensal = 0.0108
    const corrigido = valorOriginal * Math.pow(1 + selicMensal, mesesDesde)
    const comDesconto = corrigido * 0.6

    return (
        <div>
            <div className="section-title">📅 Prazos e Timeline do Processo</div>
            <div className="section-sub">Cálculo automático de todos os prazos relevantes com base nas datas informadas</div>

            {events.length === 0 ? (
                <div className="alert-box info">
                    <div className="alert-title">📊 AGUARDANDO DATAS</div>
                    <div className="alert-content">Preencha as datas na aba INTAKE para visualizar a timeline e os cálculos de prazo.</div>
                </div>
            ) : (
                <div className="timeline">
                    {events.map((ev, i) => (
                        <div key={i} className={`timeline-item ${ev.status}`}>
                            <div className="tl-date">{ev.icon} {fmt(ev.date)}</div>
                            <div className="tl-title">{ev.label}</div>
                            <div className="tl-status" style={{ color: ev.status === 'expired' ? 'var(--danger)' : ev.status === 'current' ? 'var(--gold)' : 'var(--text2)' }}>
                                {ev.action || (ev.status === 'past' ? '✅ Ocorrido' : ev.status === 'expired' ? '🔴 VENCIDO' : '🔵 Futuro')}
                            </div>
                            <div className="tl-action">{ev.fundamento}</div>
                        </div>
                    ))}
                </div>
            )}

            {valorOriginal > 0 && (
                <div className="calc-card">
                    <div className="card-title" style={{ marginBottom: 16 }}>💰 Calculadora de Multa Corrigida</div>
                    <div className="calc-row"><span className="calc-label">Valor original da multa</span><span className="calc-value">R$ {valorOriginal.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span></div>
                    <div className="calc-row"><span className="calc-label">Meses desde lavratura</span><span className="calc-value">{mesesDesde} meses</span></div>
                    <div className="calc-row"><span className="calc-label">Taxa SELIC estimada (mensal)</span><span className="calc-value">~1,08%</span></div>
                    <div className="calc-row"><span className="calc-label">Valor corrigido estimado</span><span className="calc-value gold">R$ {corrigido.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span></div>
                    <div className="calc-row"><span className="calc-label">Com desconto PGFN à vista (40%)</span><span className="calc-value success">R$ {comDesconto.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span></div>
                    <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text2)' }}>
                        * Valores estimados. Consulte o portal REGULARIZE (PGFN) para valores exatos e opções de transação.
                    </div>
                </div>
            )}
        </div>
    )
}
