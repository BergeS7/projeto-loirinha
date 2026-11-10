# Integração front-end ↔ backend Firebase

Referência do backend: [`docs/backend/BACKEND.md`](backend/BACKEND.md), um resumo do
[PDF de 21/10/2026](backend/documentacao_backend_firebase_emulator_frontend.pdf), que é a fonte da verdade.
Contrato atual do front: [`docs/API.md`](API.md).

## 1. Onde estamos

| Peça | Situação |
| --- | --- |
| Front (raiz do repositório) | PWA de passageiro funcionando com dados simulados. As telas leem `services/transit` pelos hooks de `hooks/transit.ts` |
| Backend (`backend/`) | Firebase com check-in, rotas por frota e telemetria. Atende **motorista e dono de frota** |
| Ponte já pronta no front | `src/config/firebase.ts` (SDK + emuladores) e `src/services/backend/` (login, as 8 callables, telemetria em tempo real e tradução de erros). **Ainda não é usada pelas telas** |

O front fala "português e camelCase" (`Linha`, `Ponto`, `Onibus`) e espera REST. O backend usa callables e
Firestore/RTDB em snake_case, e exige login para tudo. A ponte converte uma coisa na outra, sem mudar as telas.

## 2. O que cada tela precisa x o que o backend tem

| Método do `TransitService` | Dado no backend | Situação |
| --- | --- | --- |
| `getOnibus(linhaId?)` | `/telemetry/{busId}` (posição, velocidade, status, online) + `buses/{busId}` (placa) | **Parcial.** Falta: ligação ônibus → linha visível ao passageiro, `progresso` sobre o traçado, `lotacao`, `proximoPontoId` e `minutosProximoPonto` |
| `getLinhas`, `getLinha` | `routes` (`name`, `color_hex_route`, `stops`) | **Bloqueado (D3).** Rota com `fleet_owner_id` só é lida pelo dono, e as 3 do export têm o campo. Faltam também `numero`, `operacao` e `intervalo` |
| `getItinerario` | `routes.stops` (`name`, `latitude`, `longitude`, `order`) | **Bloqueado (D3).** As paradas não têm `id` próprio nem `referencia` |
| `getTracado` | — | **Não existe.** É preciso gravar o traçado pelas ruas (OSRM, Valhalla ou GPS) |
| `getPontos`, `getPonto`, `getPontosProximos` | — | **Não existe.** As paradas só existem dentro de cada rota |
| `getPrevisoes` | `eta_minutes` / `predicted_arrival_ms` (funções puras, sem callable) | **Não existe (D8)** |
| `getAvisos` | — | **Não existe** |
| `buscar` | — | **Não existe.** Pode ser feito no cliente sobre linhas e pontos |

Já dá para usar hoje: login, papel do usuário, check-in e check-out, rotas do dono e do motorista, envio e
leitura de telemetria. Ou seja, as telas de **motorista** e **dono de frota** (D11) podem ser feitas agora.

## 3. Decisões que destravam o passageiro

Detalhes na seção 9 do PDF.

1. **D3, rotas para passageiro.** Proposta: uma coleção pública `lines` (ou uma callable `listLines`), mantida pelo
   backend, com número, nome, cor, horário, intervalo, paradas com `id` e traçado. A rota da frota continua privada.
2. **D4, privacidade de `buses`.** Hoje qualquer autenticado vê `active_driver_id` e `fleet_owner_id`. Proposta: o passageiro
   lê só uma projeção pública (por exemplo `public_buses/{busId}`: prefixo, linha e lotação), escrita pelo backend.
3. **Login do passageiro.** As regras exigem `auth != null`. Proposta: `signInAnonymously` para passageiros (exige
   habilitar o provedor anônimo) ou leitura via callable pública.
4. **D8, ETA.** Proposta: o backend calcula `progresso` e o próximo ponto no `sendTelemetry`, projetando o GPS no traçado, e grava
   isso no nó. O front calcula só o tempo até o ponto do usuário, sem enviar a posição dele.
5. **D5, tempo real.** Trocar o polling de 3 s (`useBusPositions`) por `onValue` em `/telemetry` (`subscribeTelemetry`).

## 4. Próximos passos sugeridos

1. Subir os emuladores com uma cópia dos dados (`docs/backend/BACKEND.md`, seção 5) e copiar `.env.example` para `.env.local`.
2. Testar a ponte: login com `motorista1@example.test`, `getMyRoute()` e `subscribeBusTelemetry("bus1", …)`.
3. Reunião de decisões D3, D4, D5, D8, D10 e D11.
4. Backend: implementar as decisões (coleção pública de linhas e pontos, projeção pública de ônibus, `progresso`).
5. Front: criar `src/services/transit/firebaseTransitService.ts`, implementando o `TransitService` com
   `src/services/backend`, e acrescentar `VITE_DATA_SOURCE=firebase` em `src/config/env.ts` e `services/transit/index.ts`.
   As telas não mudam.
6. Front: telas de motorista e dono, se o grupo decidir que o React cobre esses papéis (D11).

## 5. Regras para quem for integrar

- Nunca confie no front para segurança. Esconder um botão é só interface; quem protege é o backend.
- O papel vem de `getRole()` (claim do token), nunca de `users.role`. Depois de mudar o papel, use `getRole(true)`.
- Trate os erros pelo `reason` de `BackendError`. Com `precisaLogin`, mande o usuário para o login.
- Não use `createUserWithEmailAndPassword`: a conta nasce sem claim e sem `users/{uid}`, e nenhuma function a aceita.
- Nunca aponte o front ou os scripts para o projeto real sem combinar. `loirinha-1a25f` é o ID de produção.
