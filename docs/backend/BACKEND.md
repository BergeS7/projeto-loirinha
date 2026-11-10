# Backend Firebase: resumo da documentação técnica

**Fonte da verdade:** [`documentacao_backend_firebase_emulator_frontend.pdf`](documentacao_backend_firebase_emulator_frontend.pdf)
(21/10/2026). Este arquivo é um resumo para consulta rápida. Em caso de dúvida ou divergência, vale o PDF.
Os guias `backend/CHECKIN_GUIDE.md` e `backend/TELEMETRY_GUIDE.md` estão **desatualizados** (veja o aviso no topo de cada um).

Etiquetas usadas: **[OK]** confirmado no código · **[PARCIAL]** existe com lacunas · **[PENDENTE]** falta implementar ·
**[DECISÃO]** depende do grupo.

## 1. Visão geral

| Serviço | Porta (emulador) | O que guarda |
| --- | --- | --- |
| Authentication | 9099 | Contas (e-mail/senha) e a custom claim `role`, que é a fonte oficial do papel |
| Firestore | 8080 | `users`, `drivers`, `buses`, `routes`, `invite_codes` |
| Realtime Database | 9000 | `/telemetry/{busId}`: última posição e saúde da conexão. Namespace `loirinha-1a25f-default-rtdb` |
| Cloud Functions (Python 3.14) | 5001 | 8 callables na região `southamerica-east1` |
| Emulator UI | 4000 (padrão do CLI) | — |

- Projeto: `loirinha-1a25f`. **É o ID real**: nunca rode `firebase deploy` por engano. Use só os comandos de emulador.
- Toda escrita passa pelas callables. As regras negam qualquer escrita direta do cliente no Firestore e no RTDB.
- Papéis (`role`): `dono_frota`, `motorista`, `passageiro`. O campo `users/{uid}.role` é só informativo e não autoriza nada.
- O mesmo ID de ônibus aparece em `buses/{busId}` (Firestore) e em `/telemetry/{busId}` (RTDB).
- Não há ligação direta entre ônibus e rota: o caminho é ônibus → `active_driver_id` → `drivers.id_route` → `routes`.

## 2. Coleções

| Caminho | Campos principais | Leitura pelo cliente |
| --- | --- | --- |
| `users/{uid}` | `name`, `email`, `role` (informativo), `fleet_owner_id` (o dono tem o próprio UID; o passageiro não tem o campo) | Só o próprio documento |
| `drivers/{id}` | `user_id`, `fleet_owner_id`, `driver_code`, `active` (precisa ser `true`), `id_route` (opcional) | O próprio motorista, ou o dono da frota |
| `buses/{busId}` | `tag_code` (único), `plate`, `model`, `capacity`, `fleet_owner_id`, `active_driver_id` (UID ou `null`) | Qualquer usuário autenticado |
| `routes/{id}` | `name`, `origin`/`destination` `{name, latitude, longitude}`, `stops` `[{name, latitude, longitude, order}]`, `color_hex_route`, `color_hex_out_route`, `fleet_owner_id` | Sem `fleet_owner_id`: qualquer autenticado. Com o campo: só o dono |
| `invite_codes/{code}` | `code`, `fleet_owner_id`, `used`, `created_at` | Negada **[PARCIAL]**: há só um protótipo FastAPI |
| `/telemetry/{busId}` (RTDB) | `lat`, `lng`, `speed` (km/h inteiro, instantânea), `heading`, `status` (`in_service`, `delayed`, `out_of_route`), `updated_at` (hora do servidor), `captured_at`, `is_online`, `connection_status` (`online`, `connection_lost`), `lat_anterior`, `long_anterior`, `distance` (hipotética) | Qualquer usuário autenticado |

"Fora de serviço" quer dizer que **não existe o nó** em `/telemetry`. Um ônibus fica `connection_lost` quando passa mais de 45 s sem envio.

## 3. Callables (`httpsCallable(functions, "<nome>")`)

| Função | Papel exigido | Entrada | Saída (sucesso) |
| --- | --- | --- | --- |
| `checkIn` | motorista | `{ tagCode }` | `{ success, busId, tagCode, plate, driverDocId, driverId, releasedBuses, message }` |
| `checkOut` | motorista | — | `{ success, driverId, releasedBuses, message }`. Não remove a telemetria |
| `createRoute` | dono_frota | `{ name, origin, destination, stops, color_hex_route, color_hex_out_route }` | `{ success, routeId, message }` |
| `setDriverRoute` | dono_frota | `{ driverId, routeId }` | `{ success, driverId, routeId, message }` |
| `getBusRoute` | dono_frota | `{ busId }` | `{ success, busId, driverDocId, route }` |
| `getMyRoute` | motorista | — (enviar campos dá erro) | `{ success, driverDocId, route }` |
| `sendTelemetry` | motorista com check-in no ônibus | `{ busId, lat, lng, speed, heading, status, captured_at?, distance? }` | `{ success, busId, updated_at, is_online, connection_status }` |
| `endTelemetry` | motorista com check-in no ônibus | `{ busId }` | `{ success, busId, removed }` |

- `monitorTelemetry` (agendada, a cada minuto) só existe fora do emulador. Localmente, quem faz esse papel é `scripts/telemetry_monitor.py`.
- Quando der erro, use `details.reason`, que é estável. Não use `message`.
- Ordem certa no fim da viagem: `endTelemetry` e depois `checkOut`.

### Catálogo de erros (`details.reason`)

| reason | code |
| --- | --- |
| `unauthenticated` | unauthenticated (refazer login) |
| `missing_role_claim`, `invalid_role`, `not_a_driver`, `not_a_fleet_owner` | permission-denied |
| `driver_record_not_found`, `driver_inactive`, `not_active_driver` | permission-denied |
| `fleet_mismatch_driver_user`, `bus_other_fleet`, `driver_other_fleet`, `route_other_fleet`, `fleet_not_owned`, `route_without_fleet` | permission-denied |
| `user_not_found`, `bus_not_found`, `driver_not_found`, `route_not_found` | not-found |
| `bus_occupied`, `already_checked_in_here`, `duplicate_driver_record`, `duplicate_tag_code`, `no_active_driver`, `driver_without_route` | failed-precondition |
| `stale_fix`, `stale_update` | failed-precondition (descartar o envio, não repetir em laço) |
| `invalid_*`, `unexpected_field`, `invalid_payload`, `null_island`, `captured_at_in_future` | invalid-argument |
| `contention` | aborted (tentar de novo) |

A tradução desses códigos para mensagens em português está em `src/services/backend/errors.ts`.

## 4. Dados de teste (export em `backend/emulator-data/`, 21/10/2026)

| Conta | Papel | Situação |
| --- | --- | --- |
| `dono@example.test` | dono_frota | Frota A (`bus1`, `bus3`) |
| `dono2@example.test` | dono_frota | Frota B (`bus2`, `bus_01`, `route001`, `route002`) |
| `motorista1@example.test` | motorista | `drv1`, ativo, está com o `bus1` (TAG-BUS-01) e tem rota |
| `motorista2@example.test` | motorista | `drv2`, ativo, sem ônibus |
| `inativo@example.test` | motorista | `drv3`, `active = false` |
| `outrafrota@example.test` | motorista | `drv4`, frota B |
| `semcadastro@example.test` | motorista | Sem documento em `drivers` |
| `passageiro@example.test` | passageiro | — |

- A senha de teste está na constante `PASSWORD` de `backend/scripts/seed_and_call.py`. São contas que só existem no emulador.
- Para testar a telemetria, use `bus1` com `motorista1`. O `bus_01` dos guias antigos é da frota B.
- Resíduos conhecidos: um ônibus com `tag_code = "TAG-None"` e sem frota, e o namespace RTDB `demo-checkin`, que é antigo. O front deve usar só `loirinha-1a25f-default-rtdb`.
- As 3 rotas do export têm `fleet_owner_id`, então **um passageiro não consegue ler nenhuma rota**.

## 5. Como rodar (dentro de `backend/`)

```powershell
# Pré-requisitos: Node + Firebase CLI, Java 21+, Python 3.14 em functions\venv
functions\venv\Scripts\python.exe -m pip install -r functions\requirements.txt -r functions\requirements-dev.txt

# Opção segura: importa uma CÓPIA dos dados e não grava de volta
Copy-Item -Recurse .\emulator-data $env:TEMP\emulator-data-copia
$env:FUNCTIONS_DISCOVERY_TIMEOUT = "90"
firebase emulators:start --only "firestore,auth,functions,database" --project loirinha-1a25f --import $env:TEMP\emulator-data-copia

# Monitor de perda de conexão (outro terminal)
functions\venv\Scripts\python.exe scripts\telemetry_monitor.py
```

- `scripts\start-emulators.ps1` usa `--export-on-exit` e **sobrescreve** `emulator-data/` ao encerrar.
- Testes (sobem emuladores vazios): `.\scripts\test-emulators.ps1`, `.\scripts\test-emulators.ps1 -E2E` e `.\scripts\test-telemetry.ps1`.
  Nunca rode `pytest` direto contra o emulador com os seus dados, porque ele apaga tudo.

## 6. Pendências e decisões do grupo

**[PARCIAL]**
- Convites (`invite_codes`).
- Campo `distance` hipotético.
- Funções `haversine_km`, `eta_minutes` e `predicted_arrival_ms` sem uso.
- Monitor de produção nunca executado.
- `checkOut` não encerra a telemetria.

**[PENDENTE]**
- Cadastro de usuários e definição de claim por function.
- ETA por passageiro.
- Deploy do monitor e das regras do RTDB.
- Teste E2E de `sendTelemetry` e `endTelemetry`.
- Revogação de token ao mudar o papel.

**[DECISÃO]** D1 a D11, detalhadas na seção 9 do PDF. As que afetam o front de passageiro:
- **D3:** como o passageiro vê as rotas.
- **D4:** privacidade de `buses`, que expõe `active_driver_id`.
- **D5:** estratégia de tempo real no mapa.
- **D8:** distância e ETA.
- **D10:** novos endpoints de leitura.
- **D11:** escopo do React em relação ao app do motorista.
