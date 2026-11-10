# Guia: telemetria GPS + heartbeat (Firebase Emulator Suite)

> **⚠️ Guia desatualizado.** A referência atual do backend é a documentação técnica de 21/10/2026:
> [`docs/backend/documentacao_backend_firebase_emulator_frontend.pdf`](../docs/backend/documentacao_backend_firebase_emulator_frontend.pdf)
> e o resumo em [`docs/backend/BACKEND.md`](../docs/backend/BACKEND.md). Quando este guia e a documentação divergirem, vale a documentação.
>
> Pontos já sabidamente desatualizados aqui:
> - O check-out **existe** (`checkOut`), mas não remove a telemetria: chame `endTelemetry` antes do `checkOut`.
> - Os exemplos usam `bus_01` (frota B, livre). Para testar com os dados do export use `bus1` com `motorista1@example.test`.
> - Em `telemetry_demo.py seed` e `old` o argumento `--bus` não tem padrão: informe sempre.
> - Caminhos antigos: rode os comandos dentro da pasta `backend/` deste repositório.

Tudo roda **localmente** nos emuladores, com o projeto `loirinha-1a25f` (Functions em `southamerica-east1`), com dados fictícios. Nenhum deploy, nada de produção.

## 1\. Arquitetura

```
Celular do ônibus ──(callable sendTelemetry, a cada 15-20 s)──▶ Cloud Function
                                                                  │ 1. uid/role vêm do token
                                                                  │ 2. valida payload
                                                                  │ 3. autoriza no FIRESTORE (checkIn já existente)
                                                                  │ 4. grava /telemetry/{bus\_id} (Admin SDK, CAS por ETag)
                                                                  ▼
                                                      Realtime Database  /telemetry
                                                                  ▲
 scripts/telemetry\_monitor.py (1 processo, varre a cada 5 s) ─────┘  marca connection\_lost se idade > 45 s
```

Decisões principais:

* **Clientes não escrevem no RTDB** (`database.rules.json`: `.write: false`). Assim `is\_online`/`connection\_status` não podem ser forjados e o motorista só envia pelo callable, que confere no Firestore: role `motorista` (claim) + `buses/{id}.active\_driver\_id == uid` + cadastro em `drivers` ativo + mesma `fleet\_owner\_id` do ônibus. O RTDB não sabe consultar o Firestore; regras diretas exigiriam copiar o vínculo motorista↔ônibus para o RTDB (segunda fonte de verdade).
* **Leitura**: qualquer usuário autenticado (igual a `buses` no Firestore).
* **Timestamp**: `updated\_at` = hora do **servidor** ao receber. O celular pode mandar `captured\_at` (hora do fix), usado só para recusar fix atrasado (> 45 s), do futuro (> 10 s) ou fora de ordem (≤ último aceito). Relógio errado/manipulado não mantém o veículo online.
* **Concorrência**: toda escrita é compare-and-swap por ETag (`get(etag=True)` + `set\_if\_unchanged`), com releitura em conflito. O monitor nunca sobrescreve uma telemetria que chegou depois da sua leitura.
* **Fim de viagem ≠ queda**: `status` só admite `in\_service | delayed | out\_of\_route`, então "fora de serviço" = **não existir nó**. `endTelemetry` remove o nó, e o monitor também remove (em vez de marcar `connection\_lost`) o nó de ônibus sem motorista ativo no Firestore.
* **Monitor central, não um por veículo**: uma varredura indexada (`.indexOn: updated\_at`) traz só os nós com idade > 45 s (≈0 linhas em regime normal).

### Intervalo de verificação

|Ambiente|Varredura|Idade máxima ao detectar|
|-|-|-|
|Local (`telemetry\_monitor.py`)|a cada **5 s**|≤ \~50 s|
|Produção (função agendada)|Cloud Scheduler tem mínimo de 1 min → 4 varreduras de 15 s por execução|≤ \~60 s|

O celular envia a cada 15-20 s; 45 s tolera 2 envios perdidos. Varrer a cada 5 s (1/9 do limite) adiciona no máximo 5 s de latência de detecção e é barato (consulta indexada). Mudar com `--interval`.

## 2\. Árvore `/telemetry/{bus\_id}`

```json
{
  "telemetry": {
    "bus\_01": {
      "lat": -3.6667,
      "lng": -45.38,
      "speed": 32.5,
      "heading": 180,
      "status": "in\_service",
      "updated\_at": 1791730800000,
      "captured\_at": 1791730799000,
      "is\_online": true,
      "connection\_status": "online"
    }
  }
}
```

Os campos pedidos estão todos; `captured\_at` é o único extra (ordenação/atraso). Faixas: `lat` \[-90, 90], `lng` \[-180, 180], `speed` \[0, 200] km/h, `heading` \[0, 359], valores finitos e numéricos (booleano não vale), (0, 0) recusado como "sem GPS", `status` ∈ {`in\_service`, `delayed`, `out\_of\_route`}. Campos extras no payload (inclusive `is\_online`, `updated\_at`, `uid`) são **recusados**.

Erros (`code` / `details.reason`): `invalid-argument` (`invalid\_lat`, `invalid\_lng`, `null\_island`, `invalid\_speed`, `invalid\_heading`, `invalid\_status`, `invalid\_bus\_id`, `invalid\_captured\_at`, `captured\_at\_in\_future`, `unexpected\_field`, `invalid\_payload`), `failed-precondition` (`stale\_fix`, `stale\_update`), `permission-denied` (`not\_a\_driver`, `missing\_role\_claim`, `invalid\_role`, `not\_active\_driver`, `driver\_inactive`, `bus\_other\_fleet`), `not-found` (`bus\_not\_found`), `unauthenticated`, `aborted` (`contention`).

## 3\. Arquivos

**Novos**

|Arquivo|Finalidade|
|-|-|
|`functions/telemetry.py`|Toda a lógica: validação, autorização, gravação com CAS, monitor (`sweep`, `expire\_node`, `run\_sweeps`). Sem dependência do runtime de Functions.|
|`database.rules.json`|Regras do RTDB: leitura autenticada em `/telemetry`, nenhuma escrita de cliente, índice em `updated\_at`.|
|`scripts/emulator\_rtdb.py`|Admin SDK ↔ RTDB/Firestore Emulators **somente** (recusa projeto sem `demo-` e host não local).|
|`scripts/telemetry\_monitor.py`|O processo de monitoramento local.|
|`scripts/telemetry\_demo.py`|Simulador manual (seed / telemetria recente / antiga / fim de viagem / mostrar).|
|`scripts/test-telemetry.ps1`|Roda os testes de telemetria dentro dos emuladores.|
|`functions/tests/test\_telemetry.py`|Lógica de negócio + monitor (relógio simulado).|
|`functions/tests/test\_telemetry\_rules.py`|Regras do RTDB via REST do emulador.|
|`functions/tests/rtdb\_support.py`|Helpers dos testes (host do emulador, JWT sem assinatura, REST).|
|`TELEMETRY\_GUIDE.md`|Este guia.|

**Modificados (somente adições)**

|Arquivo|Mudança|
|-|-|
|`firebase.json`|Bloco `"database": {"rules": "database.rules.json"}`. Portas e emuladores existentes intactos (`database` já estava em 9000).|
|`functions/main.py`|Imports + callables `sendTelemetry` e `endTelemetry` + função agendada `monitorTelemetry` (**só registrada fora do emulador**). `checkIn` intacto.|
|`scripts/start-emulators.ps1`|`--only` ganhou `database`.|

Não foram tocados: Auth, claims/roles, `firestore.rules`, `checkin.py`, `test-emulators.ps1`, testes existentes.

## 4\. Como o heartbeat funciona

1. O celular chama `sendTelemetry` a cada 15-20 s. Cada chamada válida grava o nó com `updated\_at = hora do servidor`, `is\_online=true`, `connection\_status="online"`.
2. O monitor consulta `updated\_at < agora − 45 s` e, para cada candidato, **relê** o nó e só então decide: se a idade for **estritamente > 45 s** grava `is\_online=false`, `connection\_status="connection\_lost"` (posição e `updated\_at` preservados), condicionado ao ETag lido. Se algo chegou no meio, o ETag mudou, a escrita falha, o nó é relido e o monitor desiste.
3. **Recuperação**: a próxima chamada válida de `sendTelemetry` regrava o nó com `online`. Chamada inválida, atrasada, antiga ou de motorista não autorizado é recusada antes de tocar no nó, então não restaura nada.
4. O monitor não depende de gatilho de escrita nem de leitura de usuário: é um laço por tempo.

## 5\. Comandos (PowerShell)

Pré-requisitos já usados no projeto: Firebase CLI, Java, `functions\\venv`.

**Subir os emuladores (terminal 1)**

```powershell



Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass


cd C:\\projects\\ah\_fire\\ah\_fire # OU TELEMETRIA\_AH\_FIRE/AH\_FIRE
.\\scripts\\start-emulators.ps1
```

UI: [http://127.0.0.1:4000](http://127.0.0.1:4000) (aba Realtime Database). Encerrar: `Ctrl+C`.

**Monitor (terminal 2, deixar aberto)**

```powershell
cd C:\\projects\\ah\_fire\\ah\_fire
.\\functions\\venv\\Scripts\\python.exe scripts\\telemetry\_monitor.py
```

Opções: `--interval 2`, `--once`. Encerrar: `Ctrl+C`.

**Testes** (feche o terminal 1 antes: o `emulators:exec` usa as mesmas portas)

```powershell
cd C:\\projects\\ah\_fire\\ah\_fire
.\\scripts\\test-telemetry.ps1
```

Sem o RTDB Emulator ligado, os testes de telemetria aparecem como **skipped** (é o caso de `.\\scripts\\test-emulators.ps1`, que continua igual e roda só o Firestore).

## 6\. Resultados reais dos testes

**Executado no ambiente de desenvolvimento do Claude (nuvem, sem acesso à sua máquina e sem baixar os emuladores):**

* `test\_telemetry.py` rodou contra **backends em memória** (Firestore e RTDB falsos que imitam `get(etag=True)`/`set\_if\_unchanged`), usando o arquivo de teste, o `conftest.py` e o `telemetry.py` reais: **72 passed, 0 failed, 1 skipped** (o skip é `test\_processo\_monitor\_real\_marca\_a\_perda`, que precisa do emulador).
* Teste de mutação nesse harness: inverter `>` para `>=` no limite de 45 s, remover o CAS do monitor, usar o horário do cliente em `updated\_at`, remover a checagem de ordem e remover a checagem de motorista ativo fizeram testes falharem (a primeira mutação só foi pega depois de acrescentar `test\_reavaliacao\_do\_no\_tambem\_respeita\_o\_limite\_estrito`).

**NÃO executado:** nenhum teste contra o Realtime Database Emulator/Firestore Emulator reais; `test\_telemetry\_rules.py` (regras); o processo `telemetry\_monitor.py`; o carregamento de `main.py` no Functions Emulator. **Rode `.\\scripts\\test-telemetry.ps1` e reporte falhas** — o que pode divergir do backend falso:

1. **ETag no emulador**: o código depende de `If-Match`/ETag do REST do RTDB Emulator (via Admin SDK Python). Se o emulador ignorar ETag, `test\_atualizacao\_chega\_durante\_a\_verificacao\_do\_monitor` falha e a garantia de concorrência só vale em produção.
2. **Regras**: o JWT sem assinatura em `?auth=` e o `401` para negação são o comportamento esperado do emulador, mas não foram vistos.
3. Consulta `order\_by\_child("updated\_at").end\_at(...)` incluindo nós sem `updated\_at` (teste `test\_no\_sem\_updated\_at\_valido\_nao\_fica\_online`).
4. Namespace: tudo usa o padrão `loirinha-1a25f-default-rtdb` (onde as regras do `firebase.json` valem).

## 7\. Verificação manual no emulador

1. Terminal 1: emuladores. Terminal 2: monitor. Terminal 3:

```powershell
cd C:\\projects\\ah\_fire\\ah\_fire
$py = ".\\functions\\venv\\Scripts\\python.exe"
\& $py scripts\\telemetry\_demo.py seed                 # motorista + ônibus bus\_01 (check-in feito)
\& $py scripts\\telemetry\_demo.py fresh                # telemetria RECENTE (passa por validação/autorização reais)
\& $py scripts\\telemetry\_demo.py show                 # is\_online true, connection\_status online
```

2. No navegador: [http://127.0.0.1:4000/database](http://127.0.0.1:4000/database) → `telemetry/bus\_01` (pode editar `updated\_at` à mão também).

## 8\. Simular recente, antiga e recuperação

```powershell
\& $py scripts\\telemetry\_demo.py fresh                # recente: o nó fica online e o monitor não faz nada
\& $py scripts\\telemetry\_demo.py old --age 60         # antiga: grava updated\_at = agora-60 s ainda "online"
#   -> o terminal do monitor imprime "connection\_lost: bus\_01" em até \~5 s
\& $py scripts\\telemetry\_demo.py show                 # is\_online false, connection\_status connection\_lost
\& $py scripts\\telemetry\_demo.py fresh                # RECUPERAÇÃO: volta para online
\& $py scripts\\telemetry\_demo.py end                  # fim de viagem: nó removido (monitor não marca queda)
```

Para ver a regra do limite sem esperar, use `--age 44` (continua online) e `--age 46` (cai).
`old` grava direto com Admin SDK (simula um celular que sumiu); `fresh` e `end` usam o mesmo caminho do callable.

## 9\. O que precisa ficar ativo

* **Local**: os emuladores (terminal 1) **e** `telemetry\_monitor.py` (terminal 2). Sem o monitor, nada vira `connection\_lost` (o emulador não tem Cloud Scheduler).
* **Produção** (futuro, não feito): `monitorTelemetry` (Cloud Scheduler, a cada minuto, 4 varreduras de 15 s) substitui o processo. Ele consome ≈45 s de execução por minuto; para reduzir custo, use `iterations=1` (detecção ≤ \~105 s) em `main.py`. Também é preciso ter uma instância do Realtime Database no projeto e publicar `database.rules.json`.

## 10\. Pendências para o app Flutter

* Login Firebase Auth com claim `role=motorista` e **check-in** (`checkIn`) antes de enviar.
* Serviço em primeiro plano (Android foreground service / iOS background location) chamando `sendTelemetry` a cada 15-20 s com `busId`, `lat`, `lng`, `speed` (**km/h**; `geolocator` entrega m/s → ×3,6), `heading` (0-359; trate `-1`/desconhecido), `status` e `captured\_at = DateTime.now().millisecondsSinceEpoch` do fix. Não enviar `is\_online`/`updated\_at`.
* Fila offline: enviar só o **fix mais recente**; fixes com mais de 45 s são recusados (`stale\_fix`) de propósito.
* Tratar `failed-precondition` (`stale\_update`/`stale\_fix`) como "descartar", não repetir em laço; `permission-denied` → pedir novo check-in.
* Chamar `endTelemetry` ao encerrar a viagem (e um fluxo de check-out que limpe `active\_driver\_id` — hoje **não existe** no backend).
* Passageiro/painel: ler `/telemetry/{bus\_id}` com `onValue`; `connection\_status == "connection\_lost"` → mostrar "sem sinal" com a última posição; nó ausente → "fora de serviço".
* Testar `sendTelemetry`/`endTelemetry` ponta a ponta no Functions Emulator (não coberto: depende de Auth+Functions e não pôde ser executado).

## 11\. Limitações conhecidas

* `sendTelemetry` custa 2 leituras de Firestore por envio (ônibus + cadastro do motorista); é o preço de revogar acesso na hora. Pode ser otimizado depois.
* A remoção de nó feita pelo monitor (ônibus sem motorista ativo) usa `delete` simples, não CAS; como nesse estado nenhum envio válido é possível, a janela de corrida é desprezível.
* Nós já em `connection\_lost` continuam sendo reexaminados a cada varredura (sem escrita). Para frotas grandes, convém limpar nós mortos há muito tempo.


## Posição anterior, velocidade e cálculos de ETA

* `lat_anterior` / `long_anterior`: `lat`/`lng` do nó antes da última atualização
  válida, copiados na mesma escrita condicional (ETag) que grava a posição nova.
  Na 1ª atualização os campos são omitidos (nunca coordenadas fictícias).
* `speed`: leitura instantânea do GPS, **km/h, inteiro** (arredondado ao mais
  próximo; .5 sobe). Não é velocidade média.
* Funções puras em `telemetry.py`, ainda não ligadas ao nó compartilhado porque
  não há fonte de localização do passageiro: `haversine_km` (distância em linha
  reta, km), `eta_minutes` (`distância_km / speed_kmh * 60`, minutos inteiros;
  `None` se velocidade <= 0/inválida; estimativa simplificada, sem trânsito,
  paradas nem percurso real) e `predicted_arrival_ms` (horário do servidor em
  Unix ms UTC + ETA). `distance`, `tempo_de_chegada` e `horário_previsto` por
  passageiro dependem de uma fonte confiável da posição dele (pendente).
