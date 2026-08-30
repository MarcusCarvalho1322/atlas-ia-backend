// NOVO ARQUIVO — criar em src/config.js
//
// Endereço do backend atlas-geo e token de autenticação, lidos do .env do
// Vite (arquivo `.env` na raiz do projeto, ao lado de package.json):
//
//   VITE_ATLAS_API_URL=https://atlas-geo-production.up.railway.app
//   VITE_ATLAS_API_TOKEN=<o mesmo valor de ATLAS_API_TOKEN do Railway>
//
// Em desenvolvimento local, se o .env não existir, cai para localhost:8000
// (onde o `uvicorn main:app --reload` do atlas-geo roda por padrão).
export const API_BASE = import.meta.env.VITE_ATLAS_API_URL || 'http://localhost:8000'
const API_TOKEN = import.meta.env.VITE_ATLAS_API_TOKEN || ''

export function authHeaders() {
  return API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {}
}
