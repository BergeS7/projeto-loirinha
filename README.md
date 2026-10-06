# Projeto Loirinha

PWA mobile-first para acompanhar ônibus urbanos em Santa Inês (MA). Feito com React 19, TypeScript, Vite, Tailwind CSS, React Router e Leaflet/OpenStreetMap.

## Como rodar

O projeto usa o **pnpm 10.34.3** (definido em `.mise.toml`).

```bash
npx pnpm@10.34.3 install
npx pnpm@10.34.3 dev
```

O app abre em http://localhost:8443.

| Script | O que faz |
| --- | --- |
| `dev` | Servidor de desenvolvimento |
| `build` | Build de produção, com manifest e service worker |
| `preview` | Serve o build localmente |
| `typecheck` | Verifica os tipos do TypeScript |

## Publicar na Vercel

O projeto já vem configurado ([vercel.json](vercel.json)): build com pnpm, rotas do app funcionando ao abrir links diretos e service worker sem cache, para as atualizações chegarem aos celulares.

1. Envie o código para um repositório no GitHub.
2. Na Vercel, clique em **Add New → Project**, importe o repositório e clique em **Deploy**. Não é preciso mudar nada nas configurações.
3. Sem variáveis de ambiente, o app usa os dados simulados. Para usar o backend, cadastre `VITE_DATA_SOURCE` e `VITE_API_URL` em **Settings → Environment Variables** e faça um novo deploy.

## Logo e ícones

A logo fica em `public/icons/logo.svg` (com cantos arredondados) e `public/icons/logo-maskable.svg` (fundo cheio, para o Android).
Depois de trocar esses arquivos, rode `pnpm icons` para gerar os PNGs do PWA e do iPhone.

## Dados: simulados ou backend

Por padrão, o app usa dados simulados. Para conectar a um backend:

1. Copie `.env.example` para `.env.local`.
2. Defina `VITE_DATA_SOURCE=api` e `VITE_API_URL`.
3. Em desenvolvimento, defina `API_PROXY_TARGET` para evitar problemas de CORS.

O contrato que o backend precisa seguir está em [docs/API.md](docs/API.md), incluindo as regras de geografia: pontos sobre a via, traçados pelas ruas e posição dos ônibus pelo traçado.

Os dados simulados usam a geografia real de Santa Inês (OpenStreetMap). Para regerar pontos e traçados, rode `node scripts/generate-mock-geo.mjs` (precisa de internet).

## Estrutura

```
src/
  app/          Rotas (routes.tsx) e caminhos das telas (paths.ts)
  pages/        Uma tela por arquivo. Só usa hooks e componentes
  components/   layout/, map/ e ui/ (componentes reutilizáveis)
  hooks/        transit.ts (hooks de dados), useAsyncData e hooks do navegador
  services/
    transit/    Contrato TransitService + implementação HTTP e simulada (mock/)
    preferences.ts  Favoritos e buscas recentes (localStorage)
  lib/          Utilitários sem React: http, geo, format, storage
  config/       Variáveis de ambiente (env.ts) e constantes
  types/        Tipos do domínio
  styles/       CSS global dividido por área (importado em index.css)
```

Como os dados chegam às telas:

```
página → hooks/transit.ts → services/transit (contrato) → apiTransitService (HTTP)
                                                        → mockTransitService (simulado)
```

### Regras

- Páginas não importam serviços nem dados simulados diretamente. Elas usam os hooks de `hooks/transit.ts`.
- Cálculos que o backend vai fazer (previsão de chegada, próximo ponto) ficam na implementação do serviço, não nas telas.
- Para criar uma tela nova: adicione a página em `pages/`, a rota em `app/routes.tsx` e o caminho em `app/paths.ts`.
- Para um dado novo: adicione o tipo em `types/`, o método no `TransitService`, as duas implementações (API e simulada), um hook em `hooks/transit.ts` e o endpoint em `docs/API.md`.
- Estados de carregamento, erro e vazio usam `LoadingScreen`, `ErrorState` e `EmptyState`.
