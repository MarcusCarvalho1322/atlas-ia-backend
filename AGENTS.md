# AGENTS.md — instruções para assistentes de código neste projeto

Leia este arquivo antes de alterar qualquer coisa. Ele existe porque várias
decisões deste repositório parecem arbitrárias e não são.

## O que é

ATLAS-IA analisa autos de infração ambiental federal do IBAMA. Faz duas coisas:

1. **Auditoria** — aplica um protocolo de 60 itens de verificação sobre as peças
   de um processo administrativo e produz duas saídas separadas (ver "A fronteira").
2. **Prospecção** — minera diariamente a base pública do IBAMA, identifica autos
   com prazo de defesa em curso, ranqueia e enriquece com dados da Receita Federal.

Em produção: <https://atlas-geo.onrender.com> · console em `/console`.

## Estrutura

```
ATLAS-IA/                     ← raiz do repositório Git
├── main.py                   rotas da API (FastAPI)
├── catalogo.py               motor de auditoria
├── catalogo.json             ⚠ O ATIVO DO NEGÓCIO — 9 módulos, 60 itens, 28 teses
├── prospeccao.py             mineração e ranqueamento da base do IBAMA
├── rotina.py                 rotina diária + agendador interno
├── enriquecimento.py         consulta CNPJ na Receita Federal (via BrasilAPI)
├── geo_service.py            cruzamento com satélite — INPE DETER + PRODES
├── ai_service.py             geração de diagnóstico e peças (API da Anthropic)
├── models.py  db.py          tabelas e conexão (SQLAlchemy)
├── web/console-prospeccao.html   console da equipe — servido em GET /console
├── frontend/                 aplicativo React do cliente (Vite)
├── docs/                     documentação e histórico
└── render.yaml  Dockerfile  requirements.txt
```

**O backend fica na RAIZ de propósito.** O Render publica a partir da raiz do
repositório. Mover `main.py` para uma subpasta quebra o deploy em produção.
Não reorganize isso sem antes mudar o `rootDir` no painel do Render.

## A fronteira que não pode ser cruzada

O dono do produto **não é advogado**. O que se vende é constatação técnica, não
parecer jurídico — atividade privativa de advogado (Lei 8.906/94, art. 1º).

| Rota | Quem consome | O que pode conter |
|---|---|---|
| `/api/laudo-tecnico` | consumidor final | só constatação verificável |
| `/api/auditoria` | uso interno | tudo, inclusive teses e taxas |
| `/api/anexo-juridico` | advogado constituído | qualificação jurídica completa |

Regras que **não** podem ser afrouxadas:

- A separação é imposta **no servidor**, em `catalogo.py`. Nunca mova essa
  decisão para o front-end — seria contornável pelo navegador.
- O laudo técnico não pode conter tese, taxa de êxito, jurisprudência, nem valor
  projetado por probabilidade. Se você adicionar campo ao laudo, verifique isso.
- O build do cliente (`frontend/`, modo `cliente`) não deve sequer conter a
  string `/api/auditoria`. Isso é verificável: compile e procure no bundle.
- Taxas de êxito **nunca são somadas** entre teses. O motor usa o máximo
  (`max(teses, key=taxa)`). Somar produz número sem significado.

## Dados: nunca inventar

Todo dado vem de fonte pública oficial e citável: IBAMA Dados Abertos, INPE
TerraBrasilis, Receita Federal. Se um dado não existe, o campo vem `null` e a
ausência é declarada — nunca estimada, nunca preenchida com plausível.

## Armadilhas já encontradas — não reintroduza

Todas estas falharam **produzindo um resultado de aparência correta**. É a
assinatura de defeito mais perigosa deste projeto: nada quebra, a tela fica
plausível, e o erro só aparece diante do cliente.

| Armadilha | O que acontecia |
|---|---|
| Eixo do filtro CQL do INPE | O WFS usa ordem `(latitude, longitude)` — o inverso do GeoJSON de saída. Ordem trocada não dá erro: devolve **zero** resultados. |
| Bioma sem acento | O CSV do IBAMA escreve `Amazonia`; o catálogo de camadas usa `Amazônia`. Comparação literal recusava 100% dos casos vindos da mineração. Normalize com `_chave_bioma`. |
| Chave duplicada do IBAMA | Nem `NUM_AUTO_INFRACAO` nem `SEQ_AUTO_INFRACAO` são únicos — o IBAMA mantém linhas canceladas ao lado das vivas. Deduplique por `DT_ULT_ALTERACAO`. |
| Resposta fora do vocabulário | Valor diferente de `ok`/`fail`/`na` era descartado em silêncio e saía laudo com zero não conformidades. Hoje `respostas_ignoradas` e `laudo_integro` denunciam. |
| Escala do índice na IA | `SCORE: 12/100` sozinho era lido como nota escolar e invertia a conclusão. `_score_texto` escreve a direção da escala por extenso. |
| Banco não vinculado | Sem `DATABASE_URL` o serviço sobe e responde 200 em tudo, gravando em SQLite efêmero. `descrever_banco()` expõe o estado real em `GET /`. |
| Valor da multa | O IBAMA publica `302746,89` (vírgula decimal, sem separador de milhar). Exibir arredondado mostra cifra legal para mais. |

## Como rodar

**Backend** (Python 3.11+):

```bash
pip install -r requirements.txt
copy .env.example .env          # e preencha
uvicorn main:app --reload --port 8000
```

**Front-end** (Node 20+):

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

**Console da equipe**: abra `web/console-prospeccao.html` no navegador, ou
`http://localhost:8000/console` com o backend rodando.

## Variáveis de ambiente

| Variável | Para quê |
|---|---|
| `DATABASE_URL` | Postgres. Sem ela, cai para SQLite efêmero — nunca em produção. |
| `ATLAS_API_TOKEN` | senha mestra (herdada, ainda válida) |
| `ATLAS_API_TOKENS` | uma senha por pessoa: `nome:senha,nome:senha` |
| `ANTHROPIC_API_KEY` | geração de diagnóstico e peças |
| `ROTINA_DIARIA_HORA` | hora UTC da mineração diária (`09` = 06h de Brasília) |
| `BASE_IBAMA_DIR` | onde os CSVs do IBAMA ficam em disco |
| `ALLOWED_ORIGINS` | CORS |

## Convenções

- **Português** em comentários, nomes de função e mensagens. O dono do produto
  não é desenvolvedor e precisa conseguir ler o código.
- Comentário explica **por que**, não o que. Se um trecho parece estranho, o
  comentário deve dizer qual bug ele evita.
- Mensagem de commit em português, explicando a consequência do defeito — não só
  o que mudou.
- Publicação é automática: `git push` para `main` republica no Render em ~3 min.

## Antes de dar por pronto

1. O backend sobe sem erro e `GET /` mostra `"dialeto": "postgresql"`.
2. `GET /console` responde 200.
3. `cd frontend && npm run build` compila.
4. O bundle do cliente **não** contém `/api/auditoria` nem `api.anthropic.com`.
5. Nenhum segredo entrou no Git (`git ls-files | grep -i env`).
