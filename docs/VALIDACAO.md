# Validação e manutenção

## Resultado da implementação — 10/11/2026

- TypeScript: aprovado.
- Frontend: 13 testes aprovados.
- Backend puro: 9 testes aprovados.
- Firestore/RTDB locais vazios (`demo-loirinha`): 471 testes aprovados, 19 opcionais pulados por ausência de Auth/Functions nesses emuladores de teste.
- Build: aprovado, manifesto e service worker gerados. Permanece um aviso de tamanho no chunk do SDK Firebase (~676 kB antes de gzip), separado por import dinâmico do caminho inicial.
- Ruff: módulos Python novos aprovados em lint e formatação.
- Navegador: linha, acompanhamento, busca, ônibus inexistente e fallback de GPS conferidos; layout desktop e 390×844 inspecionados. O mapa agora observa mudanças de tamanho para recalcular tiles e enquadramento.

A captura local de conferência fica em `.artifacts/linha-mobile.png` (ignorada pelo Git). Não houve deploy, uso de credenciais reais ou alteração dos exports de emuladores existentes. Instalação física do PWA e E2E com Auth/Functions continuam como homologação específica do ambiente de destino.

## Frontend

Atualização de contas: frontend com 18 testes aprovados e backend puro com 16 testes aprovados. As cinco callables novas tiveram a região `southamerica-east1` conferida pelo runtime Python. Login, cadastro e recuperação foram inspecionados no navegador sem configurar credenciais reais; o envio fica desabilitado quando não há Firebase configurado. O E2E de criação Auth, entrega de e-mail e permissões GPS continua dependente dos emuladores/ambiente configurados, conforme [CONTAS.md](CONTAS.md).

```powershell
pnpm install --frozen-lockfile
pnpm typecheck
pnpm test
pnpm build
```

Vitest usa jsdom e não contata Firebase real. Os testes cobrem consultas mais lentas que o polling, cancelamento ao trocar de recurso, preservação de dados após falha, preferências locais corrompidas, timeout Firebase, expiração de GPS, vínculo de linha e encerramento de listeners.

`pnpm-workspace.yaml` fixa `re2js` em 2.9.1: o lock original apontava para uma publicação do mesmo dia rejeitada pela política de idade mínima. A proteção continua ativa. Postinstall do Firebase util e protobufjs fica negado; o esbuild usa seu instalador para verificar o binário dos testes. As configurações equivalentes para pnpm 10 e 11 estão no mesmo arquivo.

O formatador foi atualizado de oxfmt 0.2 para 0.40: a versão antiga removia separadores de tipos inline ao usar `semi: false`. O projeto mantém essa preferência em `.oxfmtrc.json` e verifica a saída com TypeScript.

## Backend sem emuladores

Na raiz do repositório:

```powershell
py -3.14 -m venv backend/functions/venv
backend/functions/venv/Scripts/python.exe -m pip install -r backend/functions/requirements.txt -r backend/functions/requirements-dev.txt
backend/functions/venv/Scripts/python.exe -m unittest discover -s backend/tests_unit -v
```

Esses testes não carregam exports, credenciais ou serviços externos. Cobrem catálogo, referências inválidas, privacidade, projeção, ausência de ETA quando parado/fora da rota e corrida entre heartbeat e exclusão.

## Backend com emuladores

Requer Java 21+, Python 3.14 e Firebase CLI. Use um projeto `demo-*` com bancos vazios, sem export-on-exit. Os testes apagam os dados do emulador de teste antes de cada caso: não rode sobre um ambiente com trabalho que precise ser preservado.

Exemplo na pasta `backend`, com o CLI instalado:

```powershell
$env:GCLOUD_PROJECT = 'demo-loirinha'
firebase emulators:exec --only 'firestore,database' --project demo-loirinha 'functions/venv/Scripts/python.exe -m pytest functions/tests --ignore=functions/tests/fluxo -q'
```

O CLI define os hosts e instala as regras. Os testes opcionais de Auth/Functions são pulados quando esses emuladores não estão presentes. Para o E2E operacional completo, use `scripts/test-emulators.ps1 -E2E` com os emuladores locais apropriados. O protótipo `tests/fluxo` é separado da aplicação Firebase e exige suas próprias dependências.

Os testes de regras verificam passageiro sem acesso a `buses` privado, motorista ativo/dono com acesso legítimo e catálogo somente leitura para autenticados. O teste de passageiro grava catálogo no Firestore e valida a projeção real no RTDB. Na suíte de distance_decay, `null` é comparado após a normalização do RTDB; `NaN` é testado na função pura porque JSON não o representa.

## Conferência manual

| Cenário                               | Resultado esperado                                                  |
| ------------------------------------- | ------------------------------------------------------------------- |
| Mock                                  | Aviso de demonstração, navegação e mapas funcionais                 |
| Ônibus inexistente                    | Indisponível/fora de serviço, sem previsão infinita                 |
| API responde em mais de 3 s           | Consulta termina; não há cancelamento contínuo                      |
| API falha depois de carregar          | Últimos dados e aviso, com retry                                    |
| GPS negado ou indisponível            | Centro de Santa Inês e explicação                                   |
| Sem conexão                           | Aviso global; previsões identificadas como antigas                  |
| Ônibus sem heartbeat por mais de 45 s | Sem sinal, última posição conhecida e sem ETA                       |
| Ônibus parado/fora do traçado         | Previsão indisponível; GPS bruto fora do traçado                    |
| Catálogo vazio                        | Listas vazias, sem fabricar linhas ou veículos                      |
| Tela 390×844 e desktop                | Conteúdo legível, painel e navegação acessíveis                     |
| PWA de produção                       | Manifesto, ícones e service worker gerados; rotas diretas funcionam |

Instalação nativa do PWA e atualização em aparelhos reais dependem do navegador/SO e devem fazer parte da homologação antes do deploy. O build e os testes automatizados não substituem essa conferência física.
