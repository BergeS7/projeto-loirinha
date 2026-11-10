# Backend Firebase: Projeto Loirinha

Cloud Functions em Python 3.14, Firestore, Realtime Database e Authentication, rodando no **Firebase Emulator Suite**
(projeto `loirinha-1a25f`, região `southamerica-east1`).

**Documentação atual:** [`../docs/backend/BACKEND.md`](../docs/backend/BACKEND.md), um resumo do
[PDF de 21/10/2026](../docs/backend/documentacao_backend_firebase_emulator_frontend.pdf).
Os guias `CHECKIN_GUIDE.md` e `TELEMETRY_GUIDE.md` estão desatualizados. Use-os só como apoio.

> ⚠️ `loirinha-1a25f` é o ID **real** do projeto. Não rode `firebase deploy` nem comandos sem os emuladores.

## Estrutura

```
backend/
  firebase.json, .firebaserc        Emuladores, functions, regras e alvo do RTDB
  firestore.rules                   Regras do Firestore (nenhuma escrita de cliente)
  database.rules.json               Regras do RTDB (/telemetry: leitura com login, sem escrita)
  firestore.indexes.json
  functions/
    main.py                         As 8 callables + monitorTelemetry (só em produção)
    checkin.py                      checkIn / checkOut
    fleet_routes.py                 createRoute / setDriverRoute / getBusRoute / getMyRoute
    telemetry.py                    sendTelemetry / endTelemetry / monitor
    roles.py                        Papéis (custom claim role)
    tests/                          pytest contra os emuladores (tests/fluxo = protótipo de convites)
  scripts/                          Seeds, consultas, demonstrações e monitor local (Python/PowerShell)
    legado/seed_and_call1.py        Versão antiga do seed (projeto demo-checkin). Não use
  emulator-data/                    Export dos emuladores (contas e dados fictícios de 21/10/2026)
  projeto-inovacao/                 Ferramenta Node para ler e definir a custom claim role (Admin SDK)
```

## Rodar localmente (PowerShell, dentro de `backend/`)

```powershell
python -m venv functions\venv
functions\venv\Scripts\python.exe -m pip install -r functions\requirements.txt -r functions\requirements-dev.txt

# Sobe os 4 emuladores com uma CÓPIA dos dados (emulator-data/ fica intacta)
Copy-Item -Recurse .\emulator-data $env:TEMP\emulator-data-copia
$env:FUNCTIONS_DISCOVERY_TIMEOUT = "90"
firebase emulators:start --only "firestore,auth,functions,database" --project loirinha-1a25f --import $env:TEMP\emulator-data-copia
```

- `scripts\start-emulators.ps1` faz o mesmo, mas com `--export-on-exit`: ao encerrar, ele **sobrescreve** `emulator-data/`.
- Monitor de perda de conexão (local): `functions\venv\Scripts\python.exe scripts\telemetry_monitor.py`.
- Testes (sobem emuladores vazios; feche os outros antes): `.\scripts\test-emulators.ps1`, `.\scripts\test-emulators.ps1 -E2E`, `.\scripts\test-telemetry.ps1`.
- Pré-requisitos: Node + Firebase CLI, Java 21+ e Python 3.14.

## O que mudou ao trazer para este repositório

- O backend saiu da raiz do zip para `backend/`. Os caminhos relativos dos scripts continuam valendo dentro desta pasta.
- Saíram `projeto-inovacao.zip` (80 MB, quase todo de `node_modules`) e `custom-claims.zip`, que duplicavam
  `projeto-inovacao/`, além de `__pycache__`.
- O PDF foi para `docs/backend/`.
- `scripts/redefinir_senha_motorista.py` agora lê a senha da variável `NOVA_SENHA`, em vez de deixá-la no código.
- Os guias ganharam um aviso de desatualização com os pontos conhecidos.
