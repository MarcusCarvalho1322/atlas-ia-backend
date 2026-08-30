# atlas-geo — backend do ATLAS-IA

Servidor que dá ao ATLAS-IA (Sistema de Defesa Ambiental) quatro coisas que ele
não tinha: uma chave de IA que fica escondida, um banco de dados de verdade
para os casos, verificação automática por satélite via INPE, e o catálogo de
auditoria consolidado como fonte única de verdade.

## O que este serviço resolve

| Antes (só no navegador) | Depois (com o atlas-geo) |
|---|---|
| App pedia sua chave da Anthropic numa janela pop-up a cada diagnóstico/peça | Chave fica só aqui no servidor, em variável de ambiente |
| Casos salvos só no `localStorage` — somem se limpar o navegador | Casos salvos num banco Postgres real, acessível de qualquer lugar |
| Nenhuma verificação técnica automática | Cruzamento das coordenadas do caso contra DETER + PRODES (INPE) |
| **20 verificações**, escritas em duplicidade em dois arquivos do front-end | **55 verificações** em 8 módulos, num catálogo único servido pela API |

## O catálogo de auditoria

`catalogo.json` + `catalogo.py` são a fonte única de verdade das regras.

Antes, as listas viviam duplicadas: `App.jsx` guardava `NAMES/TESES/WEIGHTS/TAXAS/RISCOS`
e `IntakeTab.jsx` guardava `CHECKS/CHECK_INVERT`, alinhadas apenas pela **posição**
no array. Inserir um item no meio de uma lista e esquecer a outra fazia o sistema
exibir a tese errada para a resposta errada, sem qualquer erro visível.

**Conteúdo consolidado de duas fontes reais do próprio acervo:**

| Fonte | O que trouxe |
|---|---|
| ATLAS-IA (app React) | 20 nulidades com teses, fundamentos e taxas |
| ATLAS FORENSE v2.1 (repositórios GitHub) | 55 itens de verificação em 8 módulos + catálogo de 20 nulidades |

Resultado: **55 itens de verificação** e **28 teses** sem repetição
(10 presentes nas duas fontes, 10 exclusivas do ATLAS FORENSE, 8 exclusivas do ATLAS-IA).

**Módulos:** M1 Elementos formais do auto (12) · M2 Competência fiscalizatória (6) ·
M3 Notificação (5) · M4 Provas e laudos (8) · M5 Dosimetria da multa (6) ·
M6 Prescrição (6) · M7 CDA e execução fiscal (6) · M8 Estratégia defensiva (6)

### Regras metodológicas

**Peso por regra pública, não por arbítrio.** CRÍTICO = 10, ALTO = 7, MÉDIO = 4.
Nenhum peso foi atribuído item a item. Pontuação máxima: 448.

**Divergências ficam à vista, não são resolvidas pelo sistema.** Em 5 teses as
duas fontes registram taxas de êxito diferentes (N04, N05, N11, N17, N18).
O catálogo guarda os dois valores (`taxa` e `taxa_divergente`) com uma nota
explicando a origem de cada um. Média ou escolha arbitrária seria inventar
um dado que ninguém apurou — a decisão é do advogado responsável.

**Dois scores, ambos explícitos.** `score` mede as falhas sobre o que foi de
fato avaliado (exclui N/A); `score_absoluto` mede sobre os 448 pontos do
catálogo inteiro. Só coincidem com os 55 itens respondidos.

### Pendências registradas no próprio catálogo

O campo `teses_sem_item_de_verificacao` lista 4 teses que **não têm pergunta
correspondente** no checklist — entre elas a de maior taxa de êxito de todo o
acervo:

| Tese | Êxito | Situação |
|---|---|---|
| N14 — Exigência inconstitucional de depósito prévio para recorrer (STF SV 21) | 95% | sem item de verificação |
| N15 — Inscrição em DA durante prazo recursal | 88% | coberta pelos itens 6.5 e 7.1 |
| N17 — Responsabilidade de arrendatário/posseiro | 39% | sem item de verificação |
| N18 — Área medida divergente | 52% | sem item de verificação |
| N28 — Pequeno produtor ≤ 4 módulos fiscais | 45% | sem item de verificação |

Criar perguntas para elas exige decisão jurídica — não foram inventadas.

## Endpoints

- `GET /health` — health check
- `GET /api/catalogo` — catálogo completo (módulos, 55 itens, 28 teses)
- `POST /api/auditoria` — `{respostas: {"1.1": "ok"|"fail"|"na"}, casoId?}` → diagnóstico
- `POST /api/diagnostico` — diagnóstico estratégico por IA
- `POST /api/peca` — peça jurídica por IA (`{pecaId, formData, auditResult}`)
- `GET|POST /api/casos`, `GET|DELETE /api/casos/{id}` — casos
- `POST /api/geo/verificar` — `{lat, lon, bioma, dataFato?}` → alertas oficiais de desmatamento

Todos aceitam `Authorization: Bearer <ATLAS_API_TOKEN>` quando essa variável está definida.

## Deploy no Railway

1. No projeto **atlas-geo**: **+ New** → **GitHub Repo** → `atlas-ia-backend`.
2. **+ New** → **Database** → **Add PostgreSQL** (o Railway preenche `DATABASE_URL`).
3. Em **Variables** do serviço: `ANTHROPIC_API_KEY` e `ATLAS_API_TOKEN`.
4. **Settings → Networking → Generate Domain**.
5. Leve a URL e o token para o `.env` do front-end (ver `frontend-updates/README.md`).

## Rodando localmente

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn main:app --reload
# http://localhost:8000/health
```

## Sobre a verificação por satélite

Fonte: WFS público do INPE (TerraBrasilis), a mesma base do painel oficial —
https://terrabrasilis.dpi.inpe.br. Não exige chave nem cadastro. `geo_service.py`
documenta a peculiaridade técnica descoberta ao testar o serviço (a ordem dos
eixos lat/lon no filtro espacial, que devolve zero resultados silenciosamente
se invertida).

## Aviso

Ferramenta de apoio técnico-jurídico para profissionais habilitados. As taxas de
êxito são indicativas, baseadas no acervo citado, e não garantem resultado em
caso específico. Peças geradas por IA exigem revisão de advogado antes do
protocolo.
