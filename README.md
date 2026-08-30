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
| **20 verificações**, escritas em duplicidade em dois arquivos do front-end | **60 verificações** em 9 módulos, num catálogo único servido pela API |
| Auditoria terminava num score técnico | Score **+ exposição financeira da causa**, em reais |

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

Resultado: **60 itens de verificação** e **28 teses** sem repetição
(10 presentes nas duas fontes, 10 exclusivas do ATLAS FORENSE, 8 exclusivas do ATLAS-IA).

**Módulos:** M1 Elementos formais do auto (13) · M2 Competência fiscalizatória (6) ·
M3 Notificação (5) · M4 Provas e laudos (9) · M5 Dosimetria da multa (6) ·
M6 Prescrição (6) · M7 CDA e execução fiscal (6) · M8 Estratégia defensiva (7) ·
M9 Admissibilidade recursal e barreiras de acesso (2)

### Regras metodológicas

**Peso por regra pública, não por arbítrio.** CRÍTICO = 10, ALTO = 7, MÉDIO = 4.
Nenhum peso foi atribuído item a item. Pontuação máxima: 486.

**Divergências ficam à vista, não são resolvidas pelo sistema.** Em 5 teses as
duas fontes registram taxas de êxito diferentes (N04, N05, N11, N17, N18).
O catálogo guarda os dois valores (`taxa` e `taxa_divergente`) com uma nota
explicando a origem de cada um. Média ou escolha arbitrária seria inventar
um dado que ninguém apurou — a decisão é do advogado responsável.

**Dois scores, ambos explícitos.** `score` mede as falhas sobre o que foi de
fato avaliado (exclui N/A); `score_absoluto` mede sobre os 486 pontos do
catálogo inteiro. Só coincidem com os 60 itens respondidos.

### Lacunas fechadas na versão 1.1

A versão 1.0 registrou 4 teses **sem pergunta correspondente** no checklist — entre
elas a de maior êxito de todo o acervo. A 1.1 fechou todas, com um módulo novo:

| Tese | Êxito | Item criado |
|---|---|---|
| N14 — Depósito prévio para recorrer (STF SV 21) | 95% | **9.1** e **9.2** (módulo M9, novo) |
| N17 — Responsabilidade de arrendatário/posseiro | 39% | **1.13** |
| N18 — Área medida divergente da imputada | 52% | **4.9** |
| N28 — Pequeno produtor ≤ 4 módulos fiscais | 45% | **8.7** |

`teses_sem_item_de_verificacao` agora volta vazio: **toda tese do catálogo tem
pergunta que a aciona.** As redações precisam de validação jurídica antes do uso
com cliente.

### Exposição financeira

`exposicao_financeira` traduz a auditoria em reais: multa × taxa de êxito da tese
mais forte. **As taxas nunca são somadas entre teses** — somar probabilidades de
teses distintas produz número inflado e sem significado, mesma regra que o ARGUS
TarifaCheck adota para alíquotas. É estimativa para dimensionar a causa, não
previsão de resultado.

## Prospecção — identificação e mineração de casos

Fonte: **IBAMA · Dados Abertos — Fiscalização/Auto de Infração**
(`dadosabertos.ibama.gov.br`), 84 colunas, cobertura nacional desde 1980,
**republicado diariamente**. Não exige chave nem cadastro.

Medido sobre 2026 (execução de 30/08/2026, após deduplicação):

| | |
|---|---|
| Autos vivos (cancelados e excluídos fora) | **10.305** |
| Valor em multas | **R$ 3,18 bilhões** |
| Com coordenada — alimenta a verificação INPE | 99,5% |
| Prazo de defesa vencendo em até 5 dias | **143** (R$ 37,6 mi) |
| Mais de 3 anos entre fato e lavratura | **676** (R$ 253,0 mi) |
| Auto lavrado antes da data do fato | **253** (R$ 35,6 mi) |

### Como a rotina se comporta

**Idempotente.** Rodar duas vezes na mesma base não cria duplicata nem marca
nada como novo. Testado.

**Nunca sobrescreve decisão humana.** O status comercial de cada caso
(novo/selecionado/contatado/descartado/cliente) é preservado entre execuções.
Casos marcados como descartado ou cliente saem do boletim sozinhos.

**Detecta mudança na fonte.** Se o IBAMA alterar valor, data de ciência, data
do fato ou número do processo, a rotina reporta o campo alterado e reconcilia.

**Deduplicação.** O dataset traz mais de uma linha para o mesmo auto — versões
sucessivas do registro, e às vezes a linha cancelada ao lado da viva
(justificativa "Duplicação"). Nem `NUM_AUTO_INFRACAO` nem `SEQ_AUTO_INFRACAO`
são únicos. A ingestão mantém a versão mais recente de cada auto por
`DT_ULT_ALTERACAO`.

### Agendamento

Embutido no serviço, sem cron externo nem biblioteca extra: defina
`ROTINA_DIARIA_HORA` (0–23, UTC). Falha de execução é registrada e não derruba
o serviço; `GET /api/prospeccao/ultima-execucao` mostra o resultado do último ciclo.

### Dados pessoais

O IBAMA publica nome e CPF/CNPJ, mas o uso para prospecção comercial é
finalidade distinta da publicação original. O documento sai **mascarado por
padrão** (`***2668`) e o nome só é devolvido com `revelar_documento=true` —
para que a exposição seja sempre uma escolha registrada, não o comportamento
padrão do sistema.

## Endpoints

- `GET /health` — health check
- `GET /api/catalogo` — catálogo completo (9 módulos, 60 itens, 28 teses)
- `POST /api/auditoria` — `{respostas, valorMulta?, casoId?}` → diagnóstico
- `POST /api/diagnostico` — diagnóstico estratégico por IA
- `POST /api/peca` — peça jurídica por IA (`{pecaId, formData, auditResult}`)
- `GET|POST /api/casos`, `GET|DELETE /api/casos/{id}` — casos
- `POST /api/geo/verificar` — `{lat, lon, bioma, dataFato?}` → alertas oficiais de desmatamento
- `POST /api/laudo-tecnico` — camada do consumidor: só constatação verificável
- `POST /api/anexo-juridico` — camada do advogado: teses, fundamentos, taxas
- `POST /api/prospeccao/rotina-diaria` — baixa a base do dia, concilia e devolve o boletim
- `GET /api/prospeccao/boletim` — o boletim, sem rebaixar
- `GET /api/prospeccao/ranking` — ranking filtrável por UF, valor e sinal
- `PATCH /api/prospeccao/{num_auto}` — move o caso no funil comercial
- `GET /api/prospeccao/ultima-execucao` — quando a rotina rodou e com que resultado

Todos aceitam `Authorization: Bearer <ATLAS_API_TOKEN>` quando essa variável está definida.

## Publicação

O serviço é um container padrão (ver `Dockerfile`) e roda em qualquer
plataforma que aceite Docker ou Python. **Requisito não óbvio:** o processo
precisa ficar vivo o tempo todo, porque a rotina diária dorme e acorda dentro
dele. Plataforma que hiberna por inatividade nunca dispara a mineração — se a
sua hibernar, desligue esse comportamento ou troque o agendador embutido por um
cron externo chamando `POST /api/prospeccao/rotina-diaria`.

### Passos, em qualquer plataforma

1. Aponte o deploy para este repositório.
2. Provisione um **PostgreSQL** e garanta que `DATABASE_URL` chegue ao serviço.
3. Defina as variáveis: `ANTHROPIC_API_KEY`, `ATLAS_API_TOKEN`,
   `ROTINA_DIARIA_HORA` (0–23 UTC; 09 = 06h de Brasília) e, opcionalmente,
   `ALLOWED_ORIGINS` com o domínio do front-end.
4. Gere o domínio público.
5. Chame uma vez `POST /api/prospeccao/atualizar` para baixar a base do IBAMA
   (~116 MB; só o ano corrente é extraído).
6. Leve a URL e o token para o `.env` do front-end
   (ver `frontend-updates/README.md`).

### Dimensionamento

Baixar e ingerir a base pede folga de memória — o pacote do IBAMA é lido em
memória antes de extrair. **512 MB de RAM é o mínimo confortável**; 256 MB
tende a apertar no dia da carga. Disco: ~120 MB para o pacote mais ~25 MB por
ano extraído.

O custo relevante desta operação não é hospedagem (fica abaixo de R$ 150/mês em
qualquer plataforma séria) — é a API da Anthropic gerando peças, que escala com
cliente atendido.

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
