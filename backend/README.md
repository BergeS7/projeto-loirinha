# Backend Firebase: Projeto Loirinha

Esta pasta é **exatamente o conteúdo de `projeto-loirinha-main.zip`**, sem alterações. Só este `README.md` foi
acrescentado, e saíram do zip os arquivos duplicados `projeto-inovacao.zip` (80 MB, quase todo de `node_modules`) e
`custom-claims.zip`. O PDF que estava em `docs/` fica em `../docs/backend/`.

Cloud Functions em Python 3.14, Firestore, Realtime Database e Authentication, no **Firebase Emulator Suite**
(projeto `loirinha-1a25f`, região `southamerica-east1`).

- Documentação atual: [PDF de 21/10/2026](../docs/backend/documentacao_backend_firebase_emulator_frontend.pdf),
  com resumo em [`../docs/backend/BACKEND.md`](../docs/backend/BACKEND.md). Os guias `CHECKIN_GUIDE.md` e
  `TELEMETRY_GUIDE.md` estão desatualizados: por exemplo, dizem que o check-out não existe.
- Como o front usa este backend e como rodar tudo: [`../docs/INTEGRACAO.md`](../docs/INTEGRACAO.md).
- Resultado dos testes: [`../docs/VALIDACAO.md`](../docs/VALIDACAO.md).

> ⚠️ `loirinha-1a25f` é o ID **real** do projeto. Não rode `firebase deploy` nem comandos sem os emuladores.

## Estrutura

```
firebase.json, .firebaserc        Emuladores, functions, regras e alvo do RTDB
firestore.rules                   Regras do Firestore (nenhuma escrita de cliente)
database.rules.json               Regras do RTDB (/telemetry: leitura com login, sem escrita)
functions/
  main.py                         8 callables + monitorTelemetry (só em produção)
  checkin.py                      checkIn / checkOut
  fleet_routes.py                 createRoute / setDriverRoute / getBusRoute / getMyRoute
  telemetry.py                    sendTelemetry / endTelemetry / monitor
  roles.py                        Papéis (custom claim role)
  tests/                          pytest contra os emuladores
scripts/                          Seeds, consultas, demonstrações e monitor local
emulator-data/                    Export dos emuladores (contas e dados fictícios de 21/10/2026)
projeto-inovacao/                 Ferramenta Node para ler e definir a custom claim role
```

## Rodar localmente

Use o **Git Bash ou cmd**, dentro desta pasta:

```bash
py -V:3.14 -m venv functions/venv
functions/venv/Scripts/python.exe -m pip install -r functions/requirements.txt -r functions/requirements-dev.txt
firebase login
cp -r emulator-data "$TEMP/emulator-data-copia"
firebase emulators:start --only firestore,auth,functions,database --project loirinha-1a25f --import "$TEMP/emulator-data-copia"
```

- **Sem `firebase login`**, toda callable responde 500 e a telemetria vai para o namespace RTDB errado.
  Veja `../docs/INTEGRACAO.md`, seção 3.3.
- `scripts/start-emulators.ps1` usa `--export-on-exit` e **sobrescreve** `emulator-data/` ao encerrar.
- Pontos de atenção que já vieram no zip:
  - `scripts/redefinir_senha_motorista.py` tem uma senha de teste escrita no código;
  - `scripts/seed_and_call1.py` é uma versão antiga do seed (projeto `demo-checkin`).
