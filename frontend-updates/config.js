// NOVO ARQUIVO — criar em src/config.js
//
// Configure no arquivo `.env` na raiz do projeto (ao lado de package.json):
//
//   VITE_ATLAS_API_URL=https://seu-backend.up.railway.app
//   VITE_ATLAS_API_TOKEN=<o mesmo ATLAS_API_TOKEN do backend>
//   VITE_ATLAS_MODO=cliente        # "cliente" (padrão) ou "interno"
//
// MODO — decide qual camada o aplicativo recebe do servidor:
//
//   cliente  → chama /api/laudo-tecnico. Só constatação técnica verificável.
//              Nenhuma tese, taxa de êxito ou jurisprudência trafega até o
//              navegador. É o PADRÃO: se a variável não existir, é este.
//   interno  → chama /api/auditoria, com a camada jurídica completa. Use
//              apenas em instalação da equipe, nunca na que o cliente acessa.
//
// O padrão é o modo restrito de propósito: um esquecimento de configuração
// resulta em menos exposição, não em mais.
export const API_BASE = import.meta.env.VITE_ATLAS_API_URL || 'http://localhost:8000'
const API_TOKEN = import.meta.env.VITE_ATLAS_API_TOKEN || ''

export const MODO = import.meta.env.VITE_ATLAS_MODO === 'interno' ? 'interno' : 'cliente'
export const ENDPOINT_AUDITORIA = MODO === 'interno' ? '/api/auditoria' : '/api/laudo-tecnico'

export function authHeaders() {
  return API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {}
}
