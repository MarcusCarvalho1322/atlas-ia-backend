# atlas-geo — backend do ATLAS-IA

Servidor que dá ao ATLAS-IA (Sistema de Defesa Ambiental) três coisas que ele
não tinha: uma chave de IA que fica escondida, um banco de dados de verdade
para os casos, e verificação automática por satélite via INPE.

## O que este serviço resolve

| Antes (só no navegador) | Depois (com o atlas-geo) |
|---|---|
| App pedia sua chave da Anthropic numa janela pop-up a cada diagnóstico/peça | Chave fica só aqui no servidor, em variável de ambiente |
| Casos salvos só no `localStorage` — somem se limpar o navegador | Casos salvos num banco Postgres real, acessível de qualquer lugar |
| Nenhuma verificação técnica automática | Cruzamento automático das coordenadas do caso contra DETER + PRODES (INPE) |

## Endpoints

- `GET /health` — health check
- `POST /api/diagnostico` — gera o diagnóstico estratégico (`{formData, auditResult}`)
- `POST /api/peca` — gera uma peça jurídica (`{pecaId, formData, auditResult}`)
- `GET /api/casos` / `POST /api/casos` / `GET /api/casos/{id}` / `DELETE /api/casos/{id}` — CRUD de casos
- `POST /api/geo/verificar` — `{lat, lon, bioma, dataFato?}` → alertas oficiais de desmatamento na coordenada

Todos aceitam `Authorization: Bearer <ATLAS_API_TOKEN>` quando essa variável está definida.

## Deploy no Railway — passo a passo sem precisar programar

1. Em https://railway.app, dentro do projeto **atlas-geo**, clique em **+ New** → **Empty Service** (ou reaproveite o serviço vazio que já existe).
2. Aponte o deploy para esta pasta (`atlas-geo/`) do seu repositório — se o código ainda não está no GitHub, é só arrastar esta pasta inteira para o GitHub Desktop ou pedir para alguém subir; o Railway também aceita "Deploy from GitHub Repo" direto pelo painel.
3. Clique em **+ New** → **Database** → **Add PostgreSQL** dentro do mesmo projeto. O Railway preenche `DATABASE_URL` sozinho — não precisa copiar nada.
4. No serviço do atlas-geo, vá em **Variables** e adicione:
   - `ANTHROPIC_API_KEY` — a chave Claude (a mesma do SafraCheck.IA, se preferir)
   - `ATLAS_API_TOKEN` — invente uma senha longa qualquer
5. Em **Settings → Networking → Generate Domain**, gere a URL pública do serviço (algo como `atlas-geo-production.up.railway.app`).
6. Guarde essa URL e o `ATLAS_API_TOKEN` — são as duas informações que o front-end do ATLAS-IA (pasta `frontend-updates/` deste pacote) precisa para parar de pedir a chave da Anthropic.

## Testando localmente (opcional, antes de publicar)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn main:app --reload
# abra http://localhost:8000/health
```

## Sobre a verificação por satélite

A fonte é o WFS público do INPE (TerraBrasilis) — a mesma base que alimenta
o painel oficial deles: https://terrabrasilis.dpi.inpe.br. Não precisa de
chave de API nem de cadastro; é dado público do governo. `geo_service.py`
documenta a peculiaridade técnica descoberta ao testar o serviço (a ordem
dos eixos lat/lon do filtro espacial) para quem for dar manutenção depois.
