# Integração front-end ↔ backend Firebase

O backend em `backend/` é **exatamente o do `projeto-loirinha-main.zip`**, sem alterações; só o `README.md`
foi acrescentado. A referência do backend é o [PDF de 21/10/2026](backend/documentacao_backend_firebase_emulator_frontend.pdf),
com resumo em [`docs/backend/BACKEND.md`](backend/BACKEND.md).

## 1. O que o front usa do backend

| Tela (item **Conta**) | Backend usado | Situação |
| --- | --- | --- |
| Login, sair, recuperar senha | Firebase Authentication (e-mail e senha) | ✅ Testado nos emuladores |
| Motorista: ônibus atual | Firestore `buses` onde `active_driver_id == uid` | ✅ Testado |
| Motorista: check-in, encerrar expediente | `checkIn`, `endTelemetry` + `checkOut` | ✅ Testado (unitário + backend E2E) |
| Motorista: minha rota | `getMyRoute` | ✅ Testado |
| Motorista: envio de GPS a cada 15 s | `sendTelemetry` | ✅ Testado com GPS simulado |
| Dono: ônibus, motoristas e rotas da frota | Firestore com `where("fleet_owner_id", "==", uid)` | ✅ Testado |
| Dono: rota em andamento de um ônibus | `getBusRoute` | ✅ Testado |
| Dono: atribuir rota a motorista | `setDriverRoute` | ✅ Testado |
| Dono: cadastrar rota | `createRoute` | ✅ Testado |
| Dono e passageiro: ônibus ao vivo | RTDB `/telemetry` + Firestore `buses/{id}` (placa) | ✅ Testado |

O papel vem sempre da claim `role` do token. Cada papel só vê a própria área (`/conta/motorista`,
`/conta/frota` ou `/conta/perfil`), e o backend revalida tudo.

## 2. O que ficou com dados simulados, e por quê

As telas públicas (mapa, linhas, pontos, previsões, avisos e busca) continuam com os dados simulados de
`src/services/transit/mock`, com o aviso "Demonstração". O backend original não tem nada disso para o passageiro:

- As rotas com `fleet_owner_id` só são lidas pelo dono da frota (decisão **D3** do PDF), e todas as rotas do export têm esse campo.
- Não existem pontos com `id`, traçado pelas ruas, lotação, previsões nem avisos.
- Não há ligação direta entre ônibus e linha.

Quando o backend tiver esses dados, basta criar uma implementação do `TransitService` (como `apiTransitService.ts`).
As telas não mudam.

**O que o app não faz, porque o backend não permite:**
- cadastro de contas (não há function; uma conta criada pelo app nasceria sem papel);
- cadastrar, ativar ou desativar motoristas e ônibus;
- editar ou excluir rotas.

## 3. Como rodar tudo localmente

Pré-requisitos: Node 22+, pnpm, Firebase CLI (`npm i -g firebase-tools`), Java 21+ e Python 3.14.

### 3.1 Backend (dentro de `backend/`)

```powershell
py -V:3.14 -m venv functions\venv
functions\venv\Scripts\python.exe -m pip install -r functions\requirements.txt -r functions\requirements-dev.txt
firebase login            # IMPORTANTE, ver 3.3
Copy-Item -Recurse .\emulator-data $env:TEMP\emulator-data-copia
firebase emulators:start --only "firestore,auth,functions,database" --project loirinha-1a25f --import $env:TEMP\emulator-data-copia
```

### 3.2 Front (na raiz)

```powershell
Copy-Item .env.example .env.local    # já vem apontando para os emuladores
pnpm install
pnpm dev                             # http://localhost:8443/conta
```

Contas de teste: `motorista1@example.test`, `dono@example.test` e `passageiro@example.test`. A senha é a
constante `PASSWORD` de `backend/scripts/seed_and_call.py`.

### 3.3 Por que o `firebase login` é obrigatório

Sem login no Firebase CLI, o Functions Emulator não consegue buscar a configuração do projeto. Aparecem dois problemas,
e nenhum dos dois é bug do código:

1. **Toda callable responde 500** com "Your default credentials were not found". O Admin SDK procura credenciais do Google.
2. **A telemetria vai para o namespace errado.** O emulador grava em `loirinha-1a25f`, enquanto as regras e o front usam
   `loirinha-1a25f-default-rtdb`. O motorista recebe "Posição enviada", mas o mapa não mostra nada.

Com `firebase login` feito por uma conta com acesso ao projeto `loirinha-1a25f`, os dois somem.

Sem acesso ao projeto, dá para testar assim:
- Defina `GOOGLE_APPLICATION_CREDENTIALS` com um arquivo `authorized_user` falso. O emulador não valida esse arquivo.
- Grave no cache do CLI a URL do banco. É a chave `adminsdkconfig` em
  `~/.config/configstore/firebase-tools.json`, com
  `"databaseURL": "https://loirinha-1a25f-default-rtdb.firebaseio.com"`.

Inicie os emuladores pelo **Git Bash ou cmd**. Neste ambiente, ao iniciar pelo PowerShell, o Functions Emulator falhou
ao carregar o venv, com um erro `activate.bat ENOENT` enganoso.

### 3.4 Monitor de perda de conexão

Localmente, ninguém marca `connection_lost` se o `scripts\telemetry_monitor.py` não estiver rodando. O front já trata
isso: um ônibus sem envio há mais de 45 s aparece como **Sem sinal**, usando a hora do servidor (`.info/serverTimeOffset`).

## 4. Produção (Vercel)

Configure as variáveis do Firebase real:
- `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_DATABASE_URL` e `VITE_FIREBASE_APP_ID`;
- `VITE_USE_EMULATORS=false`.

Sem elas, a área Conta mostra "O acesso ainda não está configurado neste ambiente". O resto do app funciona com os
dados simulados.

Antes disso, o backend precisa de deploy (functions, regras e instância RTDB). O PDF lista isso como pendente, e é
responsabilidade de quem administra o projeto.

## 5. Decisões que ainda dependem do grupo

Detalhes na seção 9 do PDF:
- **D3:** passageiro ver linhas.
- **D4:** privacidade de `buses`. Hoje qualquer usuário logado vê `active_driver_id`.
- **D8:** previsão de chegada.
- **D1:** cadastro de contas.
- **D11:** confirmar se o motorista usa este app ou o app Flutter.
