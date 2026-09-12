# ATLAS-IA — Mapa do Projeto

*Onde cada coisa está, o que faz e o que é seguro mostrar a terceiros.*
Atualizado em 31 de agosto de 2026, após a consolidação numa pasta única.

---

## 1. Visão geral — três lugares, três funções

O sistema não vive num lugar só. São três, e confundi-los é a origem de quase
toda dúvida prática ("por que o site não abre?", "onde estão meus dados?").

| Onde | O que é | Como se acessa |
|---|---|---|
| **Nuvem do Render** | O motor. Recebe pedidos, minera a base do IBAMA, guarda a carteira. | `https://atlas-geo.onrender.com` — responde **JSON**, não é uma tela |
| **Seu computador** | O código-fonte e as duas telas de trabalho. | `C:\Users\marcu\ATLAS-IA\` |
| **GitHub** | A cópia versionada do motor, de onde o Render publica sozinho. | `github.com/MarcusCarvalho1322/atlas-ia-backend` (privado) |

### Por que o endereço na nuvem "não abre"

Abrir `https://atlas-geo.onrender.com` no navegador devolve isto:

```json
{"service":"ATLAS-IA · atlas-geo",
 "checks":{"anthropic_key_set":true,"auth_required":true,
           "banco":{"dialeto":"postgresql","persistente":true,"conectado":true}}}
```

**Isso é o comportamento correto, não uma falha.** Esse endereço é o motor, e
motor conversa com aplicativo, não com pessoa. O texto acima é o motor
informando que está no ar, com o banco conectado e a chave de IA ativa — é o
painel de instrumentos, não o carro.

As telas para gente são os dois atalhos na Área de Trabalho (seção 3).

---

## 2. `C:\Users\marcu\ATLAS-IA\` — a pasta única do projeto

Em 31/08 tudo foi consolidado num lugar só. Nada do projeto mora fora daqui.

```
C:\Users\marcu\ATLAS-IA\
│
├── LEIA-ME.md             ← comece por aqui
├── atlas-ia-backend\      ← O MOTOR (código do que roda na nuvem)
├── atlas-ia-app\          ← A TELA DO CLIENTE
├── atlas-console\         ← A TELA DA EQUIPE
└── documentos\            ← este mapa, a pauta de validação e o histórico
```

### 2.1 `atlas-ia-backend\` — o motor

Espelho local do que está publicado. Alterar aqui e enviar ao GitHub faz o
Render republicar sozinho, em cerca de 3 minutos.

```
atlas-ia-backend\
├── main.py               17 KB   As portas de entrada do sistema (as rotas da API)
├── catalogo.py           14 KB   O motor de auditoria: aplica o catálogo às respostas
├── catalogo.json         85 KB   O CATÁLOGO — 9 módulos, 60 itens, 28 teses, 486 pontos
├── prospeccao.py         13 KB   Mineração da base do IBAMA e ranqueamento dos casos
├── rotina.py            9,0 KB   A rotina diária: sincroniza e monta o boletim
├── enriquecimento.py    9,6 KB   Consulta CNPJ na Receita Federal (razão social, telefone)
├── geo_service.py       7,7 KB   Cruzamento com satélite — INPE DETER + PRODES
├── ai_service.py         10 KB   Geração de diagnóstico e peças (chama a Claude)
├── models.py            4,6 KB   Desenho das tabelas do banco
├── db.py                2,6 KB   Conexão com o banco + diagnóstico de qual banco está em uso
│
├── render.yaml          2,9 KB   Receita de publicação na nuvem
├── Dockerfile            274 B
├── requirements.txt      153 B   Bibliotecas necessárias
├── .env.example         1,6 KB   Modelo de configuração (SEM segredos)
├── .gitignore            520 B   O que nunca vai para o GitHub
├── README.md             13 KB   Documentação técnica
│
└── frontend-updates\            Cópia de referência das telas (origem dos arquivos)
    ├── console-prospeccao.html
    ├── config.js  App.jsx
    ├── IntakeTab.jsx  AuditoriaTab.jsx  EstrategiaTab.jsx  PecasTab.jsx  CasosTab.jsx
    └── README.md
```

> **O arquivo mais valioso da pasta é o `catalogo.json`.**
> Ele é a única fonte de verdade do que o sistema verifica: cada um dos 60
> itens carrega, lado a lado, a constatação **técnica** (o que se verifica, a
> gravidade, a providência) e a qualificação **jurídica** (a tese, o
> fundamento, o encaminhamento). Mudar uma regra do negócio é mudar este
> arquivo — não é preciso mexer em código.

### 2.2 `atlas-ia-app\` — a tela do cliente

```
atlas-ia-app\
├── index.html           A página que abre
├── package.json         Definição do projeto
├── vite.config.js       Configuração de compilação
├── .env                 ⚠ ENDEREÇO E SENHA DE ACESSO — nunca compartilhar
├── .env.example         Modelo sem segredo, esse pode ser compartilhado
└── src\
    ├── config.js        Endereço do motor + O MODO (cliente | interno)
    ├── App.jsx          Estrutura e navegação
    ├── main.jsx  index.css
    └── components\
        ├── IntakeTab.jsx        Preenchimento dos 60 itens
        ├── AuditoriaTab.jsx     Resultado — laudo técnico ou auditoria completa
        ├── EstrategiaTab.jsx    Diagnóstico gerado por IA
        ├── PecasTab.jsx         Geração das 7 peças
        ├── PrazosTab.jsx        Prazo de defesa, prescrição, correção do valor
        └── CasosTab.jsx         Carteira de casos salvos
```

**O `MODO` é a configuração mais importante de todo o sistema.**

| Modo | Rota que o aplicativo chama | O que trafega até o navegador |
|---|---|---|
| `cliente` *(padrão)* | `/api/laudo-tecnico` | Só constatação técnica verificável |
| `interno` | `/api/auditoria` | Tudo, inclusive teses e taxas de êxito |

O padrão é o modo restrito **de propósito**: um esquecimento de configuração
resulta em menos exposição, não em mais. E a separação é imposta no servidor —
não é uma escolha de tela que alguém possa contornar mexendo no navegador.

### 2.3 `atlas-console\` — a tela da equipe

```
atlas-console\
└── console-prospeccao.html   14 KB — arquivo único, abre em qualquer navegador
```

Não precisa de instalação nem compilação. É a bancada de trabalho: boletim do
dia, casos com prazo vencendo, funil comercial. Nele o **nome do autuado não
aparece** e o documento é exibido mascarado.

---

## 3. Como abrir cada coisa

Três atalhos na Área de Trabalho:

| Atalho | O que abre | Para quem |
|---|---|---|
| `1 - ATLAS Console da Equipe.cmd` | O console, direto no navegador | Equipe |
| `2 - ATLAS Aplicativo do Cliente.cmd` | O aplicativo em `localhost:5173` | Cliente / atendimento |
| `3 - ATLAS Pasta do Projeto.cmd` | A pasta do projeto | Quando precisar dos arquivos |

Na primeira vez, o console pede o endereço do motor e a senha de acesso no
topo da tela, e guarda no próprio navegador.

---

## 4. Onde os dados realmente moram

| Dado | Onde vive | Sobrevive a reinício? |
|---|---|---|
| Carteira de prospectos e funil | PostgreSQL do Render | **Sim** — comprovado |
| Base bruta do IBAMA (CSV) | Disco temporário da nuvem | Não — e é assim mesmo: é rebaixada sozinha |
| Consultas de CNPJ | Cache no banco, 30 dias | Sim |
| Preferências do console | Navegador de quem usa | Só naquele navegador |

O CNPJ de pessoa jurídica é guardado por extenso, porque é público no cadastro
da Receita Federal. **CPF de pessoa física não é guardado por extenso** — só os
quatro últimos dígitos, mascarados.

---

## 5. O que NUNCA deve sair daqui

| Item | Onde está | Por quê |
|---|---|---|
| `atlas-ia-app\.env` | `ATLAS-IA\atlas-ia-app\` | Contém a senha de acesso à API |
| Senha do banco | Painel do Render | Dá acesso direto a toda a carteira |
| `ANTHROPIC_API_KEY` | Painel do Render | Chave de cobrança |
| Repositório no GitHub | Privado | Contém o catálogo inteiro — o ativo do negócio |

O `.gitignore` do motor foi reforçado em 31/08 para barrar `*.db`, `*.sqlite`,
`.env` e bytecode. Antes disso, um arquivo de banco local (`atlas_geo.db`)
estava versionado; foi conferido antes da remoção — **tabela única, zero
registros, nenhum dado de autuado chegou a ser publicado**.

---

## 6. O que roda sozinho

| Quando | O quê |
|---|---|
| 05:45 (Brasília) | Tarefa agendada acorda o serviço — muleta enquanto o plano é gratuito |
| 06:00 (Brasília) | Mineração diária da base do IBAMA e montagem do boletim |
| A cada envio ao GitHub | O Render republica o motor sozinho |

---

## 7. Pendências com data

| Prazo | O quê |
|---|---|
| **29/09/2026** | O banco gratuito do Render **expira e é apagado** — junto vai a carteira |
| Sem data | Trocar as duas instâncias para plano pago (US$ 13/mês, plano Hobby) |
| Antes do 1º cliente | Rastrear as taxas de êxito até fonte primária (TCU, IBAMA, PGFN) |
| Antes da 1ª campanha | Validar a fronteira de captação (Prov. 205/2021 OAB) |
