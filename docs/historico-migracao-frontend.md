# Front-end — o que aplicar e onde

São duas frentes distintas, com públicos e riscos diferentes.

## 1. Console de Prospecção (equipe) — `console-prospeccao.html`

**Arquivo único, sem build.** Abre em qualquer navegador ou é servido de
qualquer lugar. Não precisa de npm, compilação nem pipeline.

É a bancada de trabalho da equipe: mostra o boletim do dia (prazo vencendo,
novos, decurso acima de 3 anos, inversão temporal), dispara a mineração e
move os casos no funil comercial.

Na primeira vez, informe no topo da tela o endereço do backend e o token —
ficam salvos no navegador. **O nome do autuado não é exibido neste console** e
o documento aparece mascarado.

## 2. ATLAS-IA (cliente) — os 7 arquivos React

Substituem os equivalentes em `atlas-ia-app/src/`.

| Arquivo | Vai para | O que muda |
|---|---|---|
| `config.js` | `src/config.js` | novo — endereço, token e **modo** |
| `App.jsx` | `src/App.jsx` | remove as regras jurídicas do código; auditoria e casos no servidor |
| `IntakeTab.jsx` | `src/components/` | busca os 60 itens do catálogo em 9 módulos; ganha Latitude/Longitude |
| `AuditoriaTab.jsx` | `src/components/` | renderiza laudo técnico **ou** auditoria completa, conforme o modo |
| `EstrategiaTab.jsx` | `src/components/` | não pede mais a chave de API ao usuário |
| `PecasTab.jsx` | `src/components/` | não pede mais a chave de API ao usuário |
| `CasosTab.jsx` | `src/components/` | busca os casos do backend, não do `localStorage` |

### O modo — a configuração mais importante

No `.env` da raiz do projeto (ao lado de `package.json`):

```
VITE_ATLAS_API_URL=https://seu-backend.up.railway.app
VITE_ATLAS_API_TOKEN=<o mesmo ATLAS_API_TOKEN do backend>
VITE_ATLAS_MODO=cliente
```

`cliente` (**padrão**) chama `/api/laudo-tecnico`: só constatação técnica
verificável. Nenhuma tese, taxa de êxito ou jurisprudência chega ao navegador.

`interno` chama `/api/auditoria`, com a camada jurídica completa. Use apenas na
instalação da equipe.

**O padrão é o modo restrito de propósito:** se a variável for esquecida, o
resultado é menos exposição, não mais.

## O que saiu do código

Antes existiam duas listas paralelas que precisavam ficar alinhadas pela posição:

```
App.jsx        →  NAMES[20]  TESES[20]  WEIGHTS[20]  TAXAS[20]  RISCOS[20]
IntakeTab.jsx  →  CHECKS[20]  CHECK_INVERT[20]
```

Inserir um item no meio de uma e esquecer a outra fazia o sistema mostrar a tese
errada para a resposta errada — sem erro visível na tela. Nada disso existe mais
no front-end.

## Casos antigos

Casos salvos antes desta mudança guardavam as respostas como lista de 20
posições. Continuam abrindo, mas **as verificações precisam ser refeitas** — o
catálogo passou de 20 para 60 itens, e remapear automaticamente inventaria
correspondências que ninguém conferiu. O app avisa isso na tela.
