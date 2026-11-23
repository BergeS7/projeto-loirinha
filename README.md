# Projeto Loirinha

PWA mobile-first para acompanhar ônibus urbanos em Santa Inês (MA). Feito com React 19, TypeScript, Vite, Tailwind CSS, React Router e Leaflet/OpenStreetMap.

## Repositório

| Pasta                                      | O que é                                                                          |
| ------------------------------------------ | -------------------------------------------------------------------------------- |
| raiz (`src/`, `public/`…)                  | Front-end PWA (este README)                                                      |
| [`backend/`](backend/README.md)            | Backend Firebase: Cloud Functions em Python, regras, scripts e dados do emulador |
| [`docs/backend/`](docs/backend/BACKEND.md) | Documentação atual do backend (PDF de 21/10/2026 + resumo)                       |
| [`docs/INTEGRACAO.md`](docs/INTEGRACAO.md) | Integração Firebase, catálogo público e configuração para dados reais            |

## Como rodar

O projeto usa o **pnpm 10.34.3** (definido em `.mise.toml`).

```bash
npx pnpm@10.34.3 install
npx pnpm@10.34.3 dev
```

O app abre em http://localhost:8443.

| Script      | O que faz                                            |
| ----------- | ---------------------------------------------------- |
| `dev`       | Servidor de desenvolvimento                          |
| `build`     | Build de produção, com manifest e service worker     |
| `preview`   | Serve o build localmente                             |
| `typecheck` | Verifica os tipos do TypeScript                      |
| `test`      | Regressões do frontend (Vitest + navegador simulado) |

## Publicar na Vercel

O projeto já vem configurado ([vercel.json](vercel.json)): build com pnpm, rotas do app funcionando ao abrir links diretos e service worker sem cache, para as atualizações chegarem aos celulares.

1. Envie o código para um repositório no GitHub.
2. Na Vercel, clique em **Add New → Project**, importe o repositório e clique em **Deploy**. Não é preciso mudar nada nas configurações.
3. Sem variáveis de ambiente, o app usa dados simulados e mostra um aviso de demonstração. Para REST, configure `VITE_DATA_SOURCE=api` e `VITE_API_URL`. Para Firebase, configure `VITE_DATA_SOURCE=firebase` e as variáveis descritas em [docs/INTEGRACAO.md](docs/INTEGRACAO.md).

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
    backend/    Login operacional, callables, telemetria e erros Firebase
    preferences.ts  Favoritos e buscas recentes (localStorage)
  lib/          Utilitários sem React: http, geo, format, storage
  config/       Variáveis de ambiente (env.ts), constantes e conexão Firebase (firebase.ts)
  types/        Tipos do domínio (transit.ts) e do backend Firebase (backend.ts)
  styles/       CSS global dividido por área (importado em index.css)
```

Como os dados chegam às telas:

```
página → hooks/transit.ts → services/transit (contrato) → apiTransitService (HTTP)
                                                        → mockTransitService (simulado)
                                                        → firebaseTransitService (catálogo público + RTDB)
```

### Regras

- Dados públicos de transporte chegam às páginas pelos hooks de `hooks/transit.ts`, sem importar mocks diretamente. Fluxos autenticados de conta e operação usam os serviços de `services/backend`.
- Cálculos que o backend vai fazer (previsão de chegada, próximo ponto) ficam na implementação do serviço, não nas telas.
- Para criar uma tela nova: adicione a página em `pages/`, a rota em `app/routes.tsx` e o caminho em `app/paths.ts`.
- Para um dado novo: adicione o tipo em `types/`, o método no `TransitService`, as duas implementações (API e simulada), um hook em `hooks/transit.ts` e o endpoint em `docs/API.md`.
- Estados de carregamento, erro e vazio usam `LoadingScreen`, `ErrorState` e `EmptyState`.

## Contas e equipe

O item **Conta** abre login, cadastro de passageiro e recuperação de senha. Após o acesso, a claim direciona para passageiro, motorista (check-in, rota e GPS) ou dono de frota (equipe e atribuição de rotas). Configuração, permissões e limites: [docs/CONTAS.md](docs/CONTAS.md).

## Confiabilidade e validação

As fontes são carregadas sob demanda. O polling não interrompe consultas lentas; o Firebase usa assinatura em tempo real e expira GPS após 45 segundos. Falhas preservam os últimos dados e exibem aviso. Posições e previsões REST não são guardadas pelo service worker nem pelo cache HTTP. Offline inclui o shell do app, mapas já visitados e o estado ainda em memória; não garante consultas novas.

O catálogo público não expõe motorista, tag, placa ou dono da frota. Lotação sem fonte é mostrada como não informada. A previsão Firebase usa distância pelo traçado e velocidade instantânea, sem inventar ETA para ônibus parado ou fora da rota.

Execute `pnpm typecheck`, `pnpm test` e `pnpm build`. Os testes backend e os cenários manuais estão em [docs/VALIDACAO.md](docs/VALIDACAO.md). Os módulos novos têm comentários de propósito, contratos e limites, além de testes de regressão.
