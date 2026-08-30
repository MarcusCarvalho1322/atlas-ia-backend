// SUBSTITUIR src/App.jsx por este arquivo.
//
// O que mudou em relação ao original (marcado com // ATLAS-GEO: nos comentários):
//   - salvarCaso() agora grava no backend (Postgres, via atlas-geo) em vez de localStorage.
//   - carregarCaso() continua igual — só muda de onde o caso veio (CasosTab busca no backend agora).
//   - INITIAL_FORM ganha latitude/longitude, para a verificação por satélite (aba Auditoria).
//   - Nada mais mudou: os 20 itens de auditoria, o cálculo de score e as 6 abas continuam idênticos.
import { useState, useCallback } from 'react'
import './index.css'
import { API_BASE, authHeaders } from './config'
import IntakeTab from './components/IntakeTab'
import AuditoriaTab from './components/AuditoriaTab'
import EstrategiaTab from './components/EstrategiaTab'
import PecasTab from './components/PecasTab'
import PrazosTab from './components/PrazosTab'
import CasosTab from './components/CasosTab'

const TABS = [
  { id: 'intake', icon: '📥', label: 'INTAKE' },
  { id: 'auditoria', icon: '🔬', label: 'AUDITORIA' },
  { id: 'estrategia', icon: '📊', label: 'ESTRATÉGIA' },
  { id: 'pecas', icon: '✍️', label: 'PEÇAS' },
  { id: 'prazos', icon: '📅', label: 'PRAZOS' },
  { id: 'casos', icon: '💼', label: 'CASOS' },
]

const INITIAL_FORM = {
  aiaNumero: '', seiNumero: '', fase: 'Defesa Administrativa 1ª Instância',
  estado: 'PA', municipio: '', orgao: 'IBAMA',
  nomeAuituado: '', cpfCnpj: '', tipoPessoa: 'PF', endereco: '', advogado: '',
  tipoInfracao: 'flora', artigo6514: '', artigo9605: '', areaHa: '',
  bioma: 'Amazônia', tipoVegetacao: '', temCAR: 'Não', numeroCAR: '',
  latitude: '', longitude: '', // ATLAS-GEO: coordenadas do RV, usadas na verificação por satélite
  valorMulta: '', dataLavratura: '', dosimetriaFundamentada: 'Não', memoriaCalculo: 'Não',
  dataFato: '', dataNotificacao: '',
  observacoes: '',
  checks: Array(20).fill(null),
}

export default function App() {
  const [activeTab, setActiveTab] = useState('intake')
  const [formData, setFormData] = useState(INITIAL_FORM)
  const [auditResult, setAuditResult] = useState(null)
  const [casoId, setCasoId] = useState(null) // ATLAS-GEO: id do caso no backend, quando já salvo
  const [toast, setToast] = useState(null)

  const showToast = useCallback((msg, type = 'info', duration = 4000) => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), duration)
  }, [])

  const updateForm = useCallback((field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }, [])

  const updateCheck = useCallback((index, value) => {
    setFormData(prev => {
      const checks = [...prev.checks]
      checks[index] = value
      return { ...prev, checks }
    })
  }, [])

  const runAudit = useCallback(() => {
    const WEIGHTS = [9,7,6,5,10,8,8,9,9,8,10,10,9,10,9,7,10,8,7,10]
    const NAMES = [
      'RV ausente','Coordenadas ausentes no RV','Metodologia ausente no RV',
      'Fotos sem georreferenciamento','Dosimetria não fundamentada',
      'Sem memória de cálculo','Sem Ordem de Serviço','Fiscal sem competência',
      'Notificação endereço errado','Notificação inválida',
      'Bis in idem (autuação estadual)','Licença estadual = incompetência IBAMA',
      'Prova só por satélite','Área não pertence ao autuado',
      'Terceiro praticou o ato','Área controvertida','PRA em andamento',
      'Laudo técnico contestando','Pequeno produtor ≤ 4 módulos','Prescrição intercorrente'
    ]
    const TESES = [
      'Violação contraditório técnico — IN IBAMA 10/2012',
      'Impossibilidade de verificação técnica do local',
      'Fragilidade probatória — sem método documentado',
      'Fotos sem valor probante — sem data/local verificável',
      'Art. 6º Lei 9.605/98 c/c art. 99 Dec. 6.514/08 — STJ REsp 1.251.697/PR',
      'Multa arbitrária — sem transparência no valor aplicado',
      'Nulidade procedimental — TRF2 Ap. 0004123-2018',
      'Incompetência funcional do agente autuador',
      'Nulidade — STJ REsp 1.340.553/MG — reabre prazo',
      'Prazo não correu — art. 26 Lei 9.784/1999',
      'LC 140/2011 art. 17 — STJ REsp 1.342.071/RJ',
      'LC 140/2011 art. 17 §3º — exclusão competência federal',
      'TRF1 AC 0014232-18.2012 — prova insuficiente',
      'Ilegitimidade passiva — imóvel de terceiro',
      'Culpa exclusiva de terceiro — excludente',
      'Área controvertida — necessidade de perícia',
      'Art. 59-A Lei 12.651/2012 — extinção punibilidade',
      'Fragilidade da prova oficial — contestação técnica',
      'Regime diferenciado — Lei 12.651/2012',
      'STF RE 669.069/MG Tema 606 — prescrição intercorrente'
    ]
    const TAXAS = [65,58,52,48,72,60,55,62,63,61,71,68,44,70,55,50,85,52,45,55]
    const RISCOS = ['CRÍTICO','ALTO','MÉDIO','MÉDIO','CRÍTICO','ALTO','ALTO','CRÍTICO','CRÍTICO','ALTO','CRÍTICO','CRÍTICO','ALTO','CRÍTICO','ALTO','MÉDIO','CRÍTICO','ALTO','MÉDIO','CRÍTICO']

    let pts = 0, total = 178, nulidades = [], conformes = [], naCount = 0
    formData.checks.forEach((v, i) => {
      if (v === 'fail') { pts += WEIGHTS[i]; nulidades.push({ name: NAMES[i], tese: TESES[i], peso: WEIGHTS[i], taxa: TAXAS[i], risco: RISCOS[i] }) }
      else if (v === 'ok') conformes.push({ name: NAMES[i], peso: WEIGHTS[i] })
      else if (v === 'na') naCount++
    })
    nulidades.sort((a, b) => b.peso - a.peso)
    const score = Math.round((pts / total) * 100)
    const result = { score, nulidades, conformes, naCount, totalPts: pts }
    setAuditResult(result)
    setActiveTab('auditoria')
    showToast(`Auditoria completa — Score: ${score}/100`, score >= 60 ? 'success' : score >= 30 ? 'warning' : 'danger')
  }, [formData.checks, showToast])

  // ATLAS-GEO: agora grava no backend (Postgres) em vez de localStorage.
  const salvarCaso = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/casos`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ formData, auditResult }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const caso = await res.json()
      setCasoId(caso.id)
      showToast('Caso salvo com sucesso!', 'success')
    } catch (e) {
      showToast(`Não foi possível salvar o caso: ${e.message}`, 'danger')
    }
  }, [formData, auditResult, showToast])

  const carregarCaso = useCallback((caso) => {
    setCasoId(caso.id)
    setFormData(caso.formData)
    if (caso.auditResult) setAuditResult(caso.auditResult)
    setActiveTab('intake')
    showToast('Caso carregado!', 'success')
  }, [showToast])

  const novoCaso = useCallback(() => {
    if (window.confirm('Limpar todos os dados do processo atual?')) {
      setFormData(INITIAL_FORM)
      setAuditResult(null)
      setCasoId(null)
      setActiveTab('intake')
    }
  }, [])

  const scoreColor = auditResult ? (auditResult.score >= 60 ? 'var(--success)' : auditResult.score >= 30 ? 'var(--gold)' : 'var(--danger)') : 'var(--text2)'

  return (
    <>
      <div className="global-header">
        <div className="header-left">
          <div>
            <div className="header-logo"><span>ATLAS</span>-IA</div>
            <div className="header-sub">Sistema de Defesa Ambiental</div>
          </div>
        </div>
        <div className="header-center">
          {formData.aiaNumero && <div className="hc-item">AIA: <span className="hc-val">{formData.aiaNumero}</span></div>}
          {auditResult && <div className="hc-item">Score: <span className="hc-val" style={{ color: scoreColor }}>{auditResult.score}/100</span></div>}
          {formData.fase && <div className="hc-item"><span className="hc-val" style={{ fontSize: 10 }}>{formData.fase}</span></div>}
        </div>
        <div className="header-right">
          <button className="btn btn-gold btn-sm" onClick={salvarCaso}>💾 Salvar</button>
          <button className="btn btn-outline btn-sm" onClick={novoCaso}>Novo</button>
        </div>
      </div>

      <nav className="tab-nav">
        {TABS.map(t => (
          <button key={t.id} className={`tab-btn ${activeTab === t.id ? 'active' : ''}`} onClick={() => setActiveTab(t.id)}>
            {t.icon} {t.label}
          </button>
        ))}
      </nav>

      <div className="main-content">
        {activeTab === 'intake' && <IntakeTab formData={formData} updateForm={updateForm} updateCheck={updateCheck} runAudit={runAudit} showToast={showToast} />}
        {activeTab === 'auditoria' && <AuditoriaTab auditResult={auditResult} formData={formData} casoId={casoId} setActiveTab={setActiveTab} showToast={showToast} />}
        {activeTab === 'estrategia' && <EstrategiaTab formData={formData} auditResult={auditResult} />}
        {activeTab === 'pecas' && <PecasTab formData={formData} auditResult={auditResult} />}
        {activeTab === 'prazos' && <PrazosTab formData={formData} />}
        {activeTab === 'casos' && <CasosTab carregarCaso={carregarCaso} showToast={showToast} />}
      </div>

      {toast && <div className={`toast ${toast.type}`}>{toast.msg}</div>}
    </>
  )
}
