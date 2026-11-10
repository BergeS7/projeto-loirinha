# Guia: check-in de motoristas (Firebase Emulator Suite)

> **⚠️ Guia desatualizado.** A referência atual do backend é a documentação técnica de 21/10/2026:
> [`docs/backend/documentacao_backend_firebase_emulator_frontend.pdf`](../docs/backend/documentacao_backend_firebase_emulator_frontend.pdf)
> e o resumo em [`docs/backend/BACKEND.md`](../docs/backend/BACKEND.md). Quando este guia e a documentação divergirem, vale a documentação.
>
> Pontos já sabidamente desatualizados aqui:
> - O check-out **existe**: a callable `checkOut` e os testes `test_checkout.py` (seção 4.4 da documentação).
> - `scripts/start-emulators.ps1` sobe **4** emuladores (firestore, auth, functions, database), não 3.
> - Rotas com `fleet_owner_id` **não** são legíveis por todos: só o dono da frota as lê; o motorista usa `getMyRoute`.
> - Caminhos como `C:\projects\ah_fire\ah_fire` são antigos: rode os comandos dentro da pasta `backend/` deste repositório.

Tudo roda **localmente**, nos **emuladores**, usando o projeto `loirinha-1a25f` (região das Functions e do Firestore: `southamerica-east1`), apenas com dados fictícios. Nenhum deploy é feito. As URLs das Functions seguem `http://127.0.0.1:5001/loirinha-1a25f/southamerica-east1/<função>`.

## 1. Arquivos criados / modificados

**Criados**
| Arquivo | Função |
|---|---|
| `functions/checkin.py` | Lógica do check-in (transação Firestore, todas as validações). Sem dependência do runtime de Functions, para ser testável. |
| `functions/tests/conftest.py` | Fixtures e dados fictícios; **aborta** se não estiver num emulador ou se o projeto não começar com `demo-`. |
| `functions/tests/test_checkin.py` | 15 cenários pedidos + extras (uid forjado, tagCode inválido, mesmo motorista duas vezes). |
| `functions/tests/test_rules.py` | Testes das Security Rules (via REST do emulador). |
| `functions/tests/test_e2e_callable.py` | Opcional: chama a Function de verdade (Auth + Functions Emulator). |
| `functions/requirements-dev.txt` | `pytest`, `requests` (só para testes). |
| `firestore.rules` | Regras: clientes não escrevem em `users`, `drivers`, `buses`, `routes`. |
| `firestore.indexes.json` | Vazio (só há consultas de igualdade em um campo; não precisam de índice composto). |
| `scripts/start-emulators.ps1` | Sobe Firestore + Auth + Functions. |
| `scripts/test-emulators.ps1` | Roda os testes dentro dos emuladores. |
| `scripts/seed_and_call.py` | Cria dados fictícios e executa check-ins manualmente. |
| `functions/roles.py` | Roles permitidas, leitura da claim `role` e `set_user_role` (merge, preserva outras claims). |
| `functions/tests/test_roles.py` | Testes sem rede de `roles.py`. |
| `scripts/emulator_auth.py` | Admin SDK ligado **somente** ao Auth Emulator (recusa host não local / projeto sem `demo-`). |
| `CHECKIN_GUIDE.md` | Este guia. |

**Modificados**
- `functions/main.py`: exemplo comentado substituído pela Function callable `checkIn`.
- `functions/requirements.txt`: adicionado `firebase_admin>=6.0.0` (já era dependência transitiva).
- `firebase.json`: bloco `firestore` (rules/indexes) e `tests`/`__pycache__` no `ignore` das Functions. Emuladores existentes preservados.
- `.firebaserc`: de `{}` para `{"projects":{"default":"loirinha-1a25f"}}` (cuidado: com o projeto real, `firebase deploy` vai para produção; use sempre `--only emulators`/`emulators:start` nos testes locais).

## 2. Como funciona o `checkIn`

Callable autenticada. Entrada: `{"tagCode": "TAG-BUS-01"}`. O UID **e a role** vêm **somente** de `request.auth` (`uid` e `token`; qualquer `uid`/`role` no payload é ignorado). **A role oficial é a custom claim `role`** do ID token (`dono_frota`, `motorista` ou `passageiro`); o campo `users/{uid}.role` do Firestore é apenas informativo/legado e **não** concede nem remove permissão (veja a seção 11). Dentro de **uma única transação** ela lê usuário, cadastro em `drivers` e ônibus; valida tudo; e só então grava `buses/{id}.active_driver_id = uid`. Se dois motoristas disputam o mesmo ônibus, um commit é abortado, a transação reexecuta, enxerga o ônibus ocupado e recusa.

Códigos de erro (`code` / `details.reason`):

| Situação | code | reason |
|---|---|---|
| Sem login | `unauthenticated` | `unauthenticated` |
| `tagCode` ausente/inválido | `invalid-argument` | `invalid_tag_code` |
| `users/{uid}` não existe | `not-found` | `user_not_found` |
| token sem claim `role` | `permission-denied` | `missing_role_claim` |
| claim `role` fora de `dono_frota`/`motorista`/`passageiro` | `permission-denied` | `invalid_role` |
| claim `role` ≠ `motorista` (inclui `dono_frota`) | `permission-denied` | `not_a_driver` |
| Sem cadastro em `drivers` (inclui `user_id` apontando para outro) | `permission-denied` | `driver_record_not_found` |
| Mais de um cadastro | `failed-precondition` | `duplicate_driver_record` |
| `active` ≠ `true` | `permission-denied` | `driver_inactive` |
| `fleet_owner_id` diverge (users × drivers) | `permission-denied` | `fleet_mismatch_driver_user` |
| `tag_code` inexistente | `not-found` | `bus_not_found` |
| `tag_code` duplicado | `failed-precondition` | `duplicate_tag_code` |
| Ônibus de outra frota | `permission-denied` | `bus_other_fleet` |
| Ônibus ocupado | `failed-precondition` | `bus_occupied` |
| Você já está no ônibus | `failed-precondition` | `already_checked_in_here` |

## 3. Pré-requisitos e dependências

- **Node.js** + **Firebase CLI**: `npm install -g firebase-tools`
- **Java 21 ou superior** no PATH (exigido pelo Firestore Emulator nas versões atuais): `java -version`
- **Python** do venv do projeto (`functions\venv`, Python 3.14). No PowerShell, na raiz do projeto:

```powershell
functions\venv\Scripts\python.exe -m pip install -r functions\requirements.txt -r functions\requirements-dev.txt
```

## 4. Iniciar os emuladores

```powershell
.\scripts\start-emulators.ps1
# equivale a: firebase emulators:start --only firestore,auth,functions --project loirinha-1a25f
```
Interface: http://127.0.0.1:4000 (Firestore em `8080`, Auth `9099`, Functions `5001`).
Se o PowerShell bloquear scripts: `powershell -ExecutionPolicy Bypass -File .\scripts\start-emulators.ps1`.

## 5. Criar os documentos fictícios

Com os emuladores no ar, em **outro** terminal:

```powershell
functions\venv\Scripts\python.exe scripts\seed_and_call.py seed
```
Cria no Auth (**com a claim `role`**, definida pelo Admin SDK antes de qualquer token) e no Firestore: dono da frota, `motorista1@` e `motorista2@` (ativos), `inativo@`, `outrafrota@`, `semcadastro@`, `passageiro@` (`@example.test`, senha `senha-ficticia-123`) e os ônibus `TAG-BUS-01` (frota do dono) e `TAG-BUS-02` (outra frota). O script só grava (`set`), não apaga nada, e pode ser repetido (claims e documentos não duplicam; outras claims existentes são preservadas).

## 6. Check-in válido (manual)

```powershell
functions\venv\Scripts\python.exe scripts\seed_and_call.py checkin motorista1@example.test TAG-BUS-01
```
Esperado: `200 {"result": {"success": true, "busId": "bus1", ...}}`.

## 7. Testes negativos (manual)

```powershell
# ônibus ocupado (rode depois do check-in acima)
functions\venv\Scripts\python.exe scripts\seed_and_call.py checkin motorista2@example.test TAG-BUS-01   # 400 FAILED_PRECONDITION / bus_occupied
functions\venv\Scripts\python.exe scripts\seed_and_call.py checkin passageiro@example.test TAG-BUS-02    # 403 / not_a_driver
functions\venv\Scripts\python.exe scripts\seed_and_call.py checkin inativo@example.test TAG-BUS-02       # 403 / driver_inactive
functions\venv\Scripts\python.exe scripts\seed_and_call.py checkin outrafrota@example.test TAG-BUS-01    # 403 / bus_other_fleet
functions\venv\Scripts\python.exe scripts\seed_and_call.py checkin semcadastro@example.test TAG-BUS-01   # 403 / driver_record_not_found
functions\venv\Scripts\python.exe scripts\seed_and_call.py checkin motorista1@example.test TAG-NAO-EXISTE # 404 / bus_not_found
```

## 8. Ver o documento do ônibus

- Pela UI: http://127.0.0.1:4000/firestore → `buses` → `bus1` → campo `active_driver_id` (deve ser o UID do motorista).
- Pelo terminal: `functions\venv\Scripts\python.exe scripts\seed_and_call.py show TAG-BUS-01`

## 9. Testes automatizados

```powershell
.\scripts\test-emulators.ps1          # lógica (15 cenários + extras) + regras
.\scripts\test-emulators.ps1 -E2E     # + chamada real da Function via Auth/Functions Emulator
```
O script usa `firebase emulators:exec`, que sobe o emulador, roda `pytest` e derruba tudo. Cada teste limpa os dados **do emulador** antes de rodar.

Como interpretar:
- `PASSED` — comportamento correto. Em toda recusa o teste também confirma que `buses/{id}` ficou **idêntico**.
- `FAILED ... documento do ônibus foi alterado` — vazamento de escrita: bug grave.
- `FAILED` em `test_rules.py` com status 200 em vez de 403 — as regras não foram carregadas (confira `firebase.json` → `firestore.rules`) ou foram afrouxadas.
- `test_14_concorrencia...` deve ter **exatamente um** vencedor e um `bus_occupied`.
- Mensagem *"FIRESTORE_EMULATOR_HOST não definido"* — rode via `emulators:exec`, nunca `pytest` solto (trava anti-produção).
- Erro de Java ao subir o Firestore Emulator — instale JDK 21+.

## 10. Security Rules — decisões

- Clientes **não escrevem** em `users`, `drivers`, `buses` nem `routes` (inclusive `active_driver_id`). Essas mudanças só ocorrem via Admin SDK/Functions, que ignoram as regras — por isso `checkIn` valida tudo.
- Leitura: `users` só o próprio; `drivers` o próprio motorista ou o dono da frota (claim `role == dono_frota` **e** `fleet_owner_id == uid`); `buses` e `routes` qualquer usuário autenticado (passageiros precisam vê-los). Ajuste se isso for sensível.
- Não havia regras anteriores a preservar. Se o app criar `users/{uid}` direto pelo cliente no cadastro, essa criação passará a ser negada: mova-a para uma Function ou adicione uma regra de `create` restrita.
- Liberar o ônibus (check-out) ainda não existe; nos testes é simulado via Admin. Implemente-o como outra Function com as mesmas validações.

## 11. Custom Claims (role oficial)

**Onde a role é definida:** no Firebase Authentication, como claim `{"role": "<papel>"}`, via Admin SDK (`firebase_admin.auth.set_custom_user_claims`), encapsulado em `functions/roles.py::set_user_role` (lê as claims atuais, altera só `role` e grava o conjunto, então outras claims são preservadas). No ambiente local isso é feito por `scripts/seed_and_call.py` (`seed` e `set-role`) usando `scripts/emulator_auth.py`, que **recusa** qualquer host que não seja local e projeto que não comece com `demo-`.

**Onde a role é lida:** `checkIn` usa `req.auth.token["role"]` (token verificado). Ordem: sem login -> `unauthenticated`; `tagCode` inválido -> `invalid_tag_code`; claim ausente -> `missing_role_claim`; claim inválida -> `invalid_role`; claim ≠ `motorista` -> `not_a_driver`; depois seguem as validações de sempre (usuário/frota, cadastro em `drivers`, ativo, ônibus, frota do ônibus, ocupação).

**`users/{uid}.role` no Firestore:** mantido nos seeds apenas como espelho **informativo/legado**. Nada no backend nem nas regras o usa para autorizar; os testes `test_c6`/`test_c7` provam que ele nem concede nem remove permissão. `users/{uid}` continua obrigatório porque fornece `fleet_owner_id`.

**Tokens desatualizados:** a claim só entra no ID token quando ele é emitido. Depois de mudar a role é preciso um novo login (ou `getIdToken(true)` no app). Um token antigo continua valendo com a role antiga até expirar (~1 h). Isto vale também para **rebaixamento**: um motorista rebaixado mantém o acesso até o token expirar, salvo se o cadastro em `drivers` for desativado (`active=false`, checado a cada chamada) ou se for implementada revogação de tokens (veja "Pendências").

### Fluxo manual (PowerShell, na raiz do projeto)

```powershell
# Terminal 1
.\scripts\start-emulators.ps1

# Terminal 2
$py = "functions\venv\Scripts\python.exe"
& $py scripts\seed_and_call.py seed                                   # cria usuários + claims
& $py scripts\seed_and_call.py claims motorista1@example.test         # claim no Auth e role num token NOVO
& $py scripts\seed_and_call.py checkin motorista1@example.test TAG-BUS-01   # 200 success
& $py scripts\seed_and_call.py checkin passageiro@example.test TAG-BUS-02   # 403 not_a_driver
& $py scripts\seed_and_call.py checkin dono@example.test TAG-BUS-01         # 403 not_a_driver
& $py scripts\seed_and_call.py seed                                   # repetir: sem duplicar nem apagar claims extras
```

Token desatualizado, passo a passo (com helpers):

```powershell
. .\scripts\helpers-checkin.ps1
& $py scripts\seed_and_call.py set-role semcadastro@example.test passageiro
$a = Get-IdToken "semcadastro@example.test"; Show-TokenClaims $a   # role no token: passageiro
Invoke-CheckIn $a "TAG-BUS-01"                                      # 403 not_a_driver
& $py scripts\seed_and_call.py set-role semcadastro@example.test motorista
Invoke-CheckIn $a "TAG-BUS-01"                                      # AINDA 403: token antigo
$b = Get-IdToken "semcadastro@example.test"; Show-TokenClaims $b    # role no token: motorista
Invoke-CheckIn $b "TAG-BUS-01"                                      # agora passa da checagem de role (falha depois: driver_record_not_found)
```

### Testes

```powershell
.\scripts\test-emulators.ps1          # lógica + regras + roles (somente Firestore Emulator)
.\scripts\test-emulators.ps1 -E2E     # + tokens reais com claims via Auth/Functions Emulator, seed repetido
```

### Pendências / limitações conhecidas
- Rebaixamento de role não invalida tokens já emitidos (ver acima). Para fechar: `auth.revoke_refresh_tokens(uid)` ao mudar a role e verificar revogação nas Functions.
- O cadastro do usuário no app (criar `users/{uid}` e definir a claim `role`) ainda não existe: a claim só pode ser definida por backend/Admin SDK. Defina antes o fluxo (Function de onboarding ou script administrativo).
- Em produção o script administrativo equivalente é `projeto-inovacao/scripts/firebase/set-custom-claim.js`; este projeto não o altera.
