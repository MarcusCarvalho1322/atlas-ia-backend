// SUBSTITUIR src/components/IntakeTab.jsx por este arquivo.
//
// Única mudança: dois campos novos na Seção C (Latitude/Longitude), lidos do
// próprio Relatório de Vistoria (o item de checklist #2 já pergunta se o RV
// tem essas coordenadas — antes elas não tinham onde ser digitadas). Servem
// de entrada para a verificação por satélite na aba Auditoria.
import { useMemo } from 'react'

const ESTADOS = ['AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO']
const FASES = ['Defesa Administrativa 1ª Instância', 'Recurso Administrativo 2ª Instância (JARI)', 'Recurso ao GABIN (3ª instância)', 'Trânsito em Julgado Administrativo', 'Dívida Ativa Inscrita (PGFN)', 'Execução Fiscal Ajuizada']
const INFRACOES = [
    { v: 'flora', l: '🌲 Flora — Desmatamento/Supressão' },
    { v: 'queimada', l: '🔥 Queimada — Incêndio/Uso de fogo' },
    { v: 'fauna', l: '🐾 Fauna — Tráfico, caça, maus-tratos' },
    { v: 'poluicao', l: '💧 Poluição — Efluentes, resíduos' },
    { v: 'uc', l: '🏞️ Unid. Conservação — Acesso irregular' },
    { v: 'mineracao', l: '⛏️ Mineração — Extração sem licença' },
    { v: 'hidricos', l: '🌊 Recursos Hídricos — APP hídrica' },
    { v: 'solo', l: '🏗️ Parcelamento do Solo — Loteamento irregular' },
]
const BIOMAS = ['Amazônia', 'Cerrado', 'Mata Atlântica', 'Caatinga', 'Pampa', 'Pantanal']
const CHECKS = [
    'O Relatório de Vistoria está juntado ao processo?',
    'O RV contém coordenadas GPS no datum SIRGAS 2000?',
    'O RV menciona metodologia de medição da área?',
    'O RV tem fotos com data e georreferenciamento?',
    'O auto contém fundamentação expressa da dosimetria?',
    'Há memória de cálculo do valor da multa?',
    'Existe Ordem de Serviço autorizando a fiscalização?',
    'O fiscal autuante é servidor com competência?',
    'A notificação foi feita no endereço correto?',
    'O autuado foi notificado pessoalmente ou por SEDEX AR?',
    'Existe autuação estadual pelos mesmos fatos? (Sim = bis in idem)',
    'O imóvel possuía licença ambiental estadual válida? (Sim = incompetência)',
    'A supressão foi baseada só em satélite sem vistoria? (Sim = prova insuficiente)',
    'Há certidão demonstrando que a área não pertence ao autuado? (Sim = ilegitimidade)',
    'Existe registro de terceiro que praticou o ato? (Sim = culpa de terceiro)',
    'A área inclui vegetação exótica ou desmatada antes de 2008? (Sim = controvertida)',
    'Há adesão ao PRA em andamento? (Sim = extinção punibilidade)',
    'Existe Laudo Técnico contestando a área do IBAMA? (Sim = fragilidade)',
    'Imóvel rural ≤ 4 módulos fiscais? (Sim = regime diferenciado)',
    'O processo ficou paralisado por mais de 3 anos? (Sim = prescrição)',
]
const CHECK_INVERT = [false, false, false, false, false, false, false, false, false, false, true, true, true, true, true, true, true, true, true, true]

function formatCPFCNPJ(v) {
    const d = v.replace(/\D/g, '')
    if (d.length <= 11) return d.replace(/(\d{3})(\d{3})(\d{3})(\d{0,2})/, '$1.$2.$3-$4').replace(/-$/, '')
    return d.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{0,2})/, '$1.$2.$3/$4-$5').replace(/-$/, '')
}

function calcPrazos(formData) {
    const { dataFato, dataLavratura, dataNotificacao } = formData
    const results = []
    if (dataNotificacao) {
        const dn = new Date(dataNotificacao)
        const prazo = new Date(dn)
        prazo.setDate(prazo.getDate() + 20)
        const hoje = new Date()
        const diff = Math.ceil((prazo - hoje) / (1000 * 60 * 60 * 24))
        results.push({ label: `Prazo de defesa: ${prazo.toLocaleDateString('pt-BR')}`, value: `${diff} dias restantes`, color: diff > 5 ? 'var(--success)' : 'var(--danger)' })
    }
    if (dataFato) {
        const df = new Date(dataFato)
        const prescricao = new Date(df)
        prescricao.setFullYear(prescricao.getFullYear() + 3)
        const hoje = new Date()
        const consumada = prescricao < hoje
        results.push({ label: `Prescrição punitiva: ${prescricao.toLocaleDateString('pt-BR')}`, value: consumada ? '⚡ CONSUMADA' : 'Pendente', color: consumada ? 'var(--success)' : 'var(--warning)' })
    }
    if (dataFato && dataLavratura) {
        const df = new Date(dataFato), dl = new Date(dataLavratura)
        const diffMs = dl - df
        const anos = Math.floor(diffMs / (365.25 * 24 * 60 * 60 * 1000))
        const meses = Math.floor((diffMs % (365.25 * 24 * 60 * 60 * 1000)) / (30 * 24 * 60 * 60 * 1000))
        const alerta = anos >= 3
        results.push({ label: `Tempo entre fato e AIA: ${anos} anos, ${meses} meses`, value: alerta ? '⚠️ POSSÍVEL PRESCRIÇÃO' : 'Dentro do prazo', color: alerta ? 'var(--danger)' : 'var(--success)' })
    }
    return results
}

export default function IntakeTab({ formData, updateForm, updateCheck, runAudit, showToast }) {
    const prazos = useMemo(() => calcPrazos(formData), [formData.dataFato, formData.dataLavratura, formData.dataNotificacao])

    return (
        <div>
            <div className="section-title">📥 Dados do Processo</div>
            <div className="section-sub">Preencha os dados do Auto de Infração Ambiental para iniciar a análise</div>

            {/* SEÇÃO A */}
            <div className="card gold-left">
                <div className="card-title">📋 Identificação do Processo</div>
                <div className="form-row">
                    <div className="form-group">
                        <label className="form-label">Número do AIA <span className="required">*</span></label>
                        <input className="form-input" placeholder="AIA-XXXXX-AAAA" value={formData.aiaNumero} onChange={e => updateForm('aiaNumero', e.target.value)} />
                    </div>
                    <div className="form-group">
                        <label className="form-label">Processo SEI/SEIA</label>
                        <input className="form-input" placeholder="XXXXX.XXXXXX/XXXX-XX" value={formData.seiNumero} onChange={e => updateForm('seiNumero', e.target.value)} />
                    </div>
                </div>
                <div className="form-row-3">
                    <div className="form-group">
                        <label className="form-label">Fase Atual</label>
                        <select className="form-select" value={formData.fase} onChange={e => updateForm('fase', e.target.value)}>
                            {FASES.map(f => <option key={f}>{f}</option>)}
                        </select>
                    </div>
                    <div className="form-group">
                        <label className="form-label">Estado</label>
                        <select className="form-select" value={formData.estado} onChange={e => updateForm('estado', e.target.value)}>
                            {ESTADOS.map(e => <option key={e}>{e}</option>)}
                        </select>
                    </div>
                    <div className="form-group">
                        <label className="form-label">Município</label>
                        <input className="form-input" placeholder="Município" value={formData.municipio} onChange={e => updateForm('municipio', e.target.value)} />
                    </div>
                </div>
                <div className="form-group">
                    <label className="form-label">Órgão Autuador</label>
                    <select className="form-select" value={formData.orgao} onChange={e => updateForm('orgao', e.target.value)}>
                        <option>IBAMA</option><option>ICMBio</option><option>FUNAI</option><option>Outro</option>
                    </select>
                </div>
            </div>

            {/* SEÇÃO B */}
            <div className="card gold-left">
                <div className="card-title">👤 Dados do Autuado</div>
                <div className="form-row">
                    <div className="form-group">
                        <label className="form-label">Nome ou Razão Social <span className="required">*</span></label>
                        <input className="form-input" value={formData.nomeAuituado} onChange={e => updateForm('nomeAuituado', e.target.value)} />
                    </div>
                    <div className="form-group">
                        <label className="form-label">CPF ou CNPJ</label>
                        <input className="form-input" placeholder="000.000.000-00" value={formData.cpfCnpj} onChange={e => updateForm('cpfCnpj', formatCPFCNPJ(e.target.value))} maxLength={18} />
                    </div>
                </div>
                <div className="form-group">
                    <label className="form-label">Tipo</label>
                    <div className="radio-group">
                        {['PF', 'PJ'].map(t => (
                            <div key={t} className={`radio-item ${formData.tipoPessoa === t ? 'active' : ''}`} onClick={() => updateForm('tipoPessoa', t)}>
                                {t === 'PF' ? 'Pessoa Física' : 'Pessoa Jurídica'}
                            </div>
                        ))}
                    </div>
                </div>
                <div className="form-row">
                    <div className="form-group">
                        <label className="form-label">Endereço completo</label>
                        <input className="form-input" value={formData.endereco} onChange={e => updateForm('endereco', e.target.value)} />
                    </div>
                    <div className="form-group">
                        <label className="form-label">Representante Legal / Advogado</label>
                        <input className="form-input" value={formData.advogado} onChange={e => updateForm('advogado', e.target.value)} />
                    </div>
                </div>
            </div>

            {/* SEÇÃO C */}
            <div className="card gold-left">
                <div className="card-title">🌿 A Infração</div>
                <div className="form-group">
                    <label className="form-label">Tipo de Infração</label>
                    <select className="form-select" value={formData.tipoInfracao} onChange={e => updateForm('tipoInfracao', e.target.value)}>
                        {INFRACOES.map(i => <option key={i.v} value={i.v}>{i.l}</option>)}
                    </select>
                </div>
                <div className="form-row">
                    <div className="form-group">
                        <label className="form-label">Artigo Dec. 6.514/2008</label>
                        <input className="form-input" placeholder="art. 50, caput" value={formData.artigo6514} onChange={e => updateForm('artigo6514', e.target.value)} />
                    </div>
                    <div className="form-group">
                        <label className="form-label">Artigo Lei 9.605/1998</label>
                        <input className="form-input" placeholder="art. 38" value={formData.artigo9605} onChange={e => updateForm('artigo9605', e.target.value)} />
                    </div>
                </div>
                <div className="form-row-3">
                    <div className="form-group">
                        <label className="form-label">Área (hectares)</label>
                        <input className="form-input" type="number" step="0.01" value={formData.areaHa} onChange={e => updateForm('areaHa', e.target.value)} />
                    </div>
                    <div className="form-group">
                        <label className="form-label">Bioma</label>
                        <select className="form-select" value={formData.bioma} onChange={e => updateForm('bioma', e.target.value)}>
                            {BIOMAS.map(b => <option key={b}>{b}</option>)}
                        </select>
                    </div>
                    <div className="form-group">
                        <label className="form-label">Vegetação suprimida</label>
                        <input className="form-input" value={formData.tipoVegetacao} onChange={e => updateForm('tipoVegetacao', e.target.value)} />
                    </div>
                </div>
                <div className="form-row">
                    <div className="form-group">
                        <label className="form-label">Possui CAR?</label>
                        <select className="form-select" value={formData.temCAR} onChange={e => updateForm('temCAR', e.target.value)}>
                            <option>Sim, com número</option><option>Não</option><option>Pendente de análise</option>
                        </select>
                    </div>
                    {formData.temCAR === 'Sim, com número' && (
                        <div className="form-group">
                            <label className="form-label">Número do CAR</label>
                            <input className="form-input" value={formData.numeroCAR} onChange={e => updateForm('numeroCAR', e.target.value)} />
                        </div>
                    )}
                </div>
                {/* ATLAS-GEO: novo — coordenadas do RV, usadas na verificação por satélite (aba Auditoria) */}
                <div className="form-row">
                    <div className="form-group">
                        <label className="form-label">Latitude do RV (graus decimais)</label>
                        <input className="form-input" type="number" step="0.0001" placeholder="ex: -1.4415" value={formData.latitude} onChange={e => updateForm('latitude', e.target.value)} />
                    </div>
                    <div className="form-group">
                        <label className="form-label">Longitude do RV (graus decimais)</label>
                        <input className="form-input" type="number" step="0.0001" placeholder="ex: -55.6572" value={formData.longitude} onChange={e => updateForm('longitude', e.target.value)} />
                    </div>
                </div>
                <div className="section-sub" style={{ marginTop: -8 }}>Copie do Relatório de Vistoria (datum SIRGAS 2000). Com esses dois campos preenchidos, a aba Auditoria confere automaticamente se há alerta oficial de desmatamento do INPE nesse ponto.</div>
            </div>

            {/* SEÇÃO D */}
            <div className="card gold-left">
                <div className="card-title">💰 A Multa</div>
                <div className="form-row">
                    <div className="form-group">
                        <label className="form-label">Valor original (R$) <span className="required">*</span></label>
                        <input className="form-input" type="number" placeholder="50000.00" value={formData.valorMulta} onChange={e => updateForm('valorMulta', e.target.value)} />
                    </div>
                    <div className="form-group">
                        <label className="form-label">Data de lavratura <span className="required">*</span></label>
                        <input className="form-input" type="date" value={formData.dataLavratura} onChange={e => updateForm('dataLavratura', e.target.value)} />
                    </div>
                </div>
                <div className="form-row">
                    <div className="form-group">
                        <label className="form-label">Dosimetria fundamentada no auto?</label>
                        <select className="form-select" value={formData.dosimetriaFundamentada} onChange={e => updateForm('dosimetriaFundamentada', e.target.value)}>
                            <option>Sim</option><option>Não</option><option>Parcialmente</option>
                        </select>
                    </div>
                    <div className="form-group">
                        <label className="form-label">Memória de cálculo?</label>
                        <select className="form-select" value={formData.memoriaCalculo} onChange={e => updateForm('memoriaCalculo', e.target.value)}>
                            <option>Sim</option><option>Não</option><option>Não verificado</option>
                        </select>
                    </div>
                </div>
                {(formData.dosimetriaFundamentada === 'Não' || formData.dosimetriaFundamentada === 'Parcialmente') && (
                    <div className="alert-box danger">
                        <div className="alert-title">⚡ NULIDADE GRAVE</div>
                        <div className="alert-content">Ausência de dosimetria fundamentada — art. 6º Lei 9.605/98 e REsp 1.251.697/PR — taxa de êxito histórica: 72%</div>
                    </div>
                )}
            </div>

            {/* SEÇÃO E */}
            <div className="card gold-left">
                <div className="card-title">📅 Datas Críticas</div>
                <div className="form-row-3">
                    <div className="form-group">
                        <label className="form-label">Data do fato <span className="required">*</span></label>
                        <input className="form-input" type="date" value={formData.dataFato} onChange={e => updateForm('dataFato', e.target.value)} />
                    </div>
                    <div className="form-group">
                        <label className="form-label">Data lavratura AIA <span className="required">*</span></label>
                        <input className="form-input" type="date" value={formData.dataLavratura} onChange={e => updateForm('dataLavratura', e.target.value)} />
                    </div>
                    <div className="form-group">
                        <label className="form-label">Data notificação <span className="required">*</span></label>
                        <input className="form-input" type="date" value={formData.dataNotificacao} onChange={e => updateForm('dataNotificacao', e.target.value)} />
                    </div>
                </div>
                {prazos.length > 0 && (
                    <div style={{ marginTop: 16 }}>
                        {prazos.map((p, i) => (
                            <div key={i} style={{ padding: '8px 12px', background: 'var(--bg3)', borderRadius: 4, marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ fontSize: 13 }}>🟡 {p.label}</span>
                                <span style={{ color: p.color, fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 600 }}>{p.value}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* SEÇÃO F — CHECKS */}
            <div className="card gold-left">
                <div className="card-title">🔍 Verificações de Nulidade</div>
                <div className="section-sub">Cada item afeta diretamente o diagnóstico e as peças geradas</div>
                {CHECKS.map((label, i) => (
                    <div key={i} className="audit-item">
                        <div style={{ flex: 1 }}>
                            <div style={{ fontSize: 13, color: 'var(--text2)' }}><strong style={{ color: 'var(--text)' }}>{i + 1}.</strong> {label}</div>
                            <div className="audit-btns">
                                <button className={`audit-btn ${CHECK_INVERT[i] ? 'fail' : 'ok'} ${formData.checks[i] === (CHECK_INVERT[i] ? 'fail' : 'ok') ? 'active' : ''}`}
                                    onClick={() => updateCheck(i, CHECK_INVERT[i] ? 'fail' : 'ok')}>
                                    {CHECK_INVERT[i] ? '✗ SIM' : '✓ SIM'}
                                </button>
                                <button className={`audit-btn ${CHECK_INVERT[i] ? 'ok' : 'fail'} ${formData.checks[i] === (CHECK_INVERT[i] ? 'ok' : 'fail') ? 'active' : ''}`}
                                    onClick={() => updateCheck(i, CHECK_INVERT[i] ? 'ok' : 'fail')}>
                                    {CHECK_INVERT[i] ? '✓ NÃO' : '✗ NÃO'}
                                </button>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* OBSERVAÇÕES */}
            <div className="card gold-left">
                <div className="card-title">📝 Observações Adicionais</div>
                <textarea className="form-textarea" placeholder="Informações não capturadas acima..." value={formData.observacoes} onChange={e => updateForm('observacoes', e.target.value)} />
            </div>

            <button className="btn btn-gold btn-lg" style={{ width: '100%', justifyContent: 'center', marginTop: 16 }} onClick={runAudit}>
                ⚡ EXECUTAR AUDITORIA COMPLETA
            </button>
        </div>
    )
}
