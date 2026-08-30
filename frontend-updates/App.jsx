// SUBSTITUIR src/App.jsx por este arquivo.
//
// MUDANÇA PRINCIPAL DESTA VERSÃO — fim da duplicação.
//
// Antes, as listas de verificação viviam escritas em DOIS lugares:
//   · aqui no App.jsx  → NAMES, TESES, WEIGHTS, TAXAS, RISCOS (20 posições cada)
//   · em IntakeTab.jsx → CHECKS, CHECK_INVERT (20 posições cada)
// As duas precisavam ficar alinhadas pela POSIÇÃO no array. Bastava inserir
// um item no meio de uma lista e esquecer a outra para o sistema passar a
// mostrar a tese errada para a resposta errada — sem erro visível.
//
// Agora o catálogo vive uma única vez, no backend, e chega por /api/catalogo.
// Este arquivo não guarda mais nenhuma regra jurídica.
//
// Também mudou: formData.checks deixa de ser um array de 20 posições e passa
// a ser um objeto { "1.1": "ok" | "fail" | "na", ... } com os 60 itens.
import { useState, useCallback } from 'react'
import './index.css'
import { API_BASE, authHeaders, ENDPOINT_AUDITORIA, MODO } from './config'
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
  latitude: '', longitude: '',
  valorMulta: '', dataLavratura: '', dosimetriaFundamentada: 'Não', memoriaCalculo: 'Não',
  dataFato: '', dataNotificacao: '',
  observacoes: '',
  checks: {},   // { "1.1": "ok" | "fail" | "na" } — preenchido conforme o catálogo
}

export default function App() {
  const [activeTab, setActiveTab] = useState('intake')
  const [formData, setFormData] = useState(INITIAL_FORM)
  const [auditResult, setAuditResult] = useState(null)
  const [casoId, setCasoId] = useState(null)
  const [auditando, setAuditando] = useState(false)
  const [toast, setToast] = useState(null)

  const showToast = useCallback((msg, type = 'info', duration = 4000) => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), duration)
  }, [])

  const updateForm = useCallback((field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }, [])

  // Agora indexado pelo id do item do catálogo ("1.1", "4.6"…), não por posição.
  const updateCheck = useCallback((itemId, value) => {
    setFormData(prev => ({ ...prev, checks: { ...prev.checks, [itemId]: value } }))
  }, [])

  // A auditoria é calculada no servidor, sobre o catálogo oficial.
  const runAudit = useCallback(async () => {
    setAuditando(true)
    try {
      const res = await fetch(`${API_BASE}${ENDPOINT_AUDITORIA}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ respostas: formData.checks, valorMulta: formData.valorMulta, casoId }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const r = await res.json()
      setAuditResult(r)
      setActiveTab('auditoria')
      // O laudo técnico (modo cliente) e a auditoria completa (modo interno)
      // têm formatos diferentes de propósito — a mensagem se adapta.
      const naoConformes = r.nao_conformes ?? r.resumo?.falhas ?? 0
      const avaliados = r.itens_verificados ?? ((r.resumo?.falhas || 0) + (r.resumo?.conformes || 0))
      const indice = r.indice_de_inconformidade ?? r.score ?? 0
      showToast(
        `Análise concluída — ${naoConformes} não conformidade(s) em ${avaliados} itens verificados`,
        indice >= 60 ? 'success' : indice >= 30 ? 'warning' : 'danger'
      )
    } catch (e) {
      showToast(`Não foi possível executar a auditoria: ${e.message}`, 'danger')
    }
    setAuditando(false)
  }, [formData.checks, formData.valorMulta, casoId, showToast])

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
    // Casos salvos antes da integração traziam checks como array de 20 posições.
    // Eles continuam abrindo, apenas sem as respostas antigas remapeadas —
    // o catálogo mudou de 20 para 55 itens e um remapeamento automático
    // inventaria correspondências que ninguém verificou.
    const checks = Array.isArray(caso.formData?.checks) ? {} : (caso.formData?.checks || {})
    setFormData({ ...INITIAL_FORM, ...caso.formData, checks })
    if (caso.auditResult) setAuditResult(caso.auditResult)
    setActiveTab('intake')
    if (Array.isArray(caso.formData?.checks)) {
      showToast('Caso carregado. As verificações precisam ser refeitas: o catálogo passou de 20 para 55 itens.', 'warning', 8000)
    } else {
      showToast('Caso carregado!', 'success')
    }
  }, [showToast])

  const novoCaso = useCallback(() => {
    if (window.confirm('Limpar todos os dados do processo atual?')) {
      setFormData(INITIAL_FORM)
      setAuditResult(null)
      setCasoId(null)
      setActiveTab('intake')
    }
  }, [])

  const indice = auditResult ? (auditResult.indice_de_inconformidade ?? auditResult.score ?? 0) : null
  const scoreColor = indice == null ? 'var(--text2)'
    : (indice >= 60 ? 'var(--success)' : indice >= 30 ? 'var(--gold)' : 'var(--danger)')

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
          {auditResult && <div className="hc-item">{MODO === 'interno' ? 'Score' : 'Inconformidade'}: <span className="hc-val" style={{ color: scoreColor }}>{indice}/100</span></div>}
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
        {activeTab === 'intake' && <IntakeTab formData={formData} updateForm={updateForm} updateCheck={updateCheck} runAudit={runAudit} auditando={auditando} showToast={showToast} />}
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
