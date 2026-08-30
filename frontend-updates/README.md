# Como aplicar estas mudanças no ATLAS-IA

Estes 7 arquivos substituem os equivalentes dentro de `atlas-ia-app/src/`.

| Arquivo | Vai para | O que muda |
|---|---|---|
| `config.js` | `src/config.js` | novo — endereço e token do backend |
| `App.jsx` | `src/App.jsx` | **remove as 5 listas de regras jurídicas do código**; auditoria e casos vão para o servidor |
| `IntakeTab.jsx` | `src/components/IntakeTab.jsx` | **remove as listas CHECKS/CHECK_INVERT**; busca os 55 itens do catálogo, agrupados em 8 módulos recolhíveis; ganha Latitude/Longitude |
| `AuditoriaTab.jsx` | `src/components/AuditoriaTab.jsx` | score por módulo, teses acionáveis sem repetição, divergências à vista, card de satélite |
| `EstrategiaTab.jsx` | `src/components/EstrategiaTab.jsx` | não pede mais a API key ao usuário |
| `PecasTab.jsx` | `src/components/PecasTab.jsx` | não pede mais a API key ao usuário |
| `CasosTab.jsx` | `src/components/CasosTab.jsx` | busca os casos do backend, não do `localStorage` |

## O que exatamente saiu do código

Antes existiam **duas listas paralelas** que precisavam ficar alinhadas pela posição:

```
App.jsx        →  NAMES[20]  TESES[20]  WEIGHTS[20]  TAXAS[20]  RISCOS[20]
IntakeTab.jsx  →  CHECKS[20]  CHECK_INVERT[20]
```

Inserir um item no meio de uma e esquecer a outra fazia o sistema mostrar a
tese errada para a resposta errada — sem erro visível na tela. Agora nada disso
existe no front-end: o catálogo vem do backend por `/api/catalogo`.

## Passo a passo

1. Copie os 7 arquivos para dentro de `atlas-ia-app`, substituindo os antigos
   (`config.js` e `App.jsx` em `src/`; os outros em `src/components/`).
2. Na raiz do projeto, ao lado de `package.json`, crie um arquivo `.env`:
   ```
   VITE_ATLAS_API_URL=https://<url-gerada-pelo-railway>
   VITE_ATLAS_API_TOKEN=<o mesmo ATLAS_API_TOKEN configurado no Railway>
   ```
3. Publique o app novamente (ou `npm run dev` para testar antes).

## Sobre casos antigos

Casos salvos antes desta mudança guardavam as respostas como uma lista de 20
posições. Eles continuam abrindo normalmente, mas **as verificações precisam ser
refeitas** — o catálogo passou de 20 para 55 itens e um remapeamento automático
inventaria correspondências que ninguém conferiu. O app avisa isso na tela ao
carregar um caso antigo.
