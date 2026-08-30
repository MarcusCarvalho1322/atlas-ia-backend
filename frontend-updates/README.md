# Como aplicar estas mudanças no ATLAS-IA

Estes 6 arquivos substituem os equivalentes dentro de `atlas-ia-app/src/`.
Nenhuma tese jurídica, regra de auditoria ou peso do score foi alterado —
só a parte técnica de "onde a chave fica" e "onde os casos são salvos".

| Arquivo novo | Substitui | O que muda |
|---|---|---|
| `config.js` | (não existia) | vai para `src/config.js` — endereço do backend |
| `App.jsx` | `src/App.jsx` | salvarCaso agora grava no atlas-geo |
| `components/EstrategiaTab.jsx` | idem | chama o backend, não pede mais API key |
| `components/PecasTab.jsx` | idem | chama o backend, não pede mais API key |
| `components/CasosTab.jsx` | idem | busca casos do backend, não do localStorage |
| `components/IntakeTab.jsx` | idem | dois campos novos: Latitude/Longitude |
| `components/AuditoriaTab.jsx` | idem | novo card "Verificação Geoespacial (INPE)" |

`AuditoriaTab.jsx`, `EstrategiaTab.jsx`, `PecasTab.jsx` e `CasosTab.jsx` vão
dentro de `src/components/`. Os outros dois (`config.js` e `App.jsx`) vão
direto em `src/`.

## Passo a passo para quem não programa

1. Peça para quem tiver acesso ao computador com a pasta `atlas-ia-app`
   (ou a você mesmo, se tiver o Claude Desktop conectado a esse computador)
   copiar estes 6 arquivos para dentro da pasta, substituindo os antigos.
2. Na raiz do projeto (ao lado de `package.json`), criar um arquivo chamado
   `.env` com duas linhas:
   ```
   VITE_ATLAS_API_URL=https://<a-url-que-o-railway-gerou>
   VITE_ATLAS_API_TOKEN=<o-mesmo-ATLAS_API_TOKEN-que-voce-colocou-no-railway>
   ```
3. Publicar o app de novo (o mesmo processo que já é usado hoje para
   colocar o ATLAS-IA no ar, ou simplesmente rodar localmente com
   `npm run dev` para testar antes).

A partir daí, o app para de pedir a chave da Anthropic em pop-up, os casos
passam a ficar salvos na nuvem, e aparece o botão de verificação por
satélite na aba Auditoria.
