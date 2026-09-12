# ATLAS-IA — comece por aqui

**Tudo do projeto está nesta pasta.** Nada mais mora fora dela.

```
C:\Users\marcu\ATLAS-IA\
```

---

## Se você só quer usar o sistema

Três atalhos na Área de Trabalho, numerados na ordem em que fazem sentido:

| Atalho | O que abre | Para quem |
|---|---|---|
| **1 — ATLAS Console da Equipe** | A bancada de trabalho: boletim do dia, casos com prazo vencendo, funil comercial | Você e a equipe |
| **2 — ATLAS Aplicativo do Cliente** | O aplicativo de análise, em `localhost:5173` | Atendimento ao interessado |
| **3 — ATLAS Pasta do Projeto** | Esta pasta | Quando precisar dos arquivos |

O primeiro abre instantaneamente — é um arquivo só, sem instalação.
O segundo leva alguns segundos para subir e abre o navegador sozinho.

---

## As quatro pastas

```
ATLAS-IA\
│
├── LEIA-ME.md              ← este arquivo
│
├── atlas-ia-backend\       O MOTOR
│                           Roda na nuvem. Minera a base do IBAMA, aplica o
│                           protocolo de 60 itens, guarda a carteira.
│                           Espelho do que está publicado no GitHub.
│
├── atlas-ia-app\           A TELA DO CLIENTE
│                           Aplicativo de análise. Recebe do motor apenas o
│                           laudo técnico — a camada jurídica não chega aqui.
│
├── atlas-console\          A TELA DA EQUIPE
│                           Arquivo único, sem instalação. Prospecção e funil.
│
└── documentos\             Mapa detalhado, pauta de validação e histórico.
```

---

## O que NÃO abre no navegador

O endereço do motor na nuvem responde em JSON, não em tela:

```json
{"service":"ATLAS-IA · atlas-geo","checks":{ ... }}
```

**Isso é o correto.** É o painel de instrumentos do motor, não uma página para
ler. Ele está dizendo que está no ar, com banco conectado e chave de IA ativa.
As telas para gente são os atalhos 1 e 2.

---

## O que roda sozinho, todo dia

| Horário (Brasília) | O quê |
|---|---|
| 05:45 | Uma tarefa agendada acorda o serviço — muleta enquanto o plano é gratuito |
| 06:00 | Mineração da base do IBAMA e montagem do boletim do dia |

Você recebe o resultado como notificação no celular.

---

## O que nunca deve sair daqui

| Item | Onde está |
|---|---|
| `atlas-ia-app\.env` | Contém a senha de acesso à API |
| Senha do banco | Só no painel do Render |
| Chave da Anthropic | Só no painel do Render |
| O repositório no GitHub | Privado — contém o catálogo inteiro |

O `catalogo.json`, dentro do motor, é o ativo do negócio: 60 itens de
verificação e 28 teses, cada um com a leitura técnica e a jurídica lado a lado.
Mudar uma regra do negócio é mudar esse arquivo — não é preciso mexer em código.

---

## Pendências com data

| Prazo | O quê |
|---|---|
| **29/09/2026** | O banco gratuito do Render **expira e é apagado** — junto vai a carteira |
| Assim que possível | Trocar as duas instâncias para plano pago (US$ 13/mês, plano Hobby) |
| Antes do 1º cliente | Rastrear as taxas de êxito até fonte primária (TCU, IBAMA, PGFN) |
| Antes da 1ª campanha | Validar a fronteira de captação — Prov. 205/2021 OAB |

As duas últimas estão na **Pauta de Validação Jurídica**, em `documentos\`.

---

*Última atualização: 31 de agosto de 2026.*
