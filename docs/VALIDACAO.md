# Validação

## Resultado de 23/11/2026 (backend original, sem alterações)

| Verificação | Resultado |
| --- | --- |
| `pnpm typecheck` | ✅ aprovado |
| `pnpm test` (Vitest) | ✅ 14 testes aprovados |
| `pnpm build` | ✅ aprovado. Aviso: o pacote da tela Conta tem ~700 kB por causa do SDK do Firebase, mas só carrega em `/conta` |
| Backend: lógica + regras + E2E das callables (`CHECKIN_E2E=1`) | ✅ 338 aprovados, 149 pulados (opcionais) |
| Backend: telemetria + regras do RTDB | ✅ 133 aprovados |
| Navegador, contra os emuladores com os dados do export | ✅ veja o roteiro abaixo |

Os testes do backend só passaram depois de contornar dois problemas do **ambiente** local, sem mudar o código.
Ambos vêm da falta de `firebase login` (veja [INTEGRACAO.md](INTEGRACAO.md), seção 3.3):
- erro 500 em todas as callables por falta de credenciais;
- telemetria gravada no namespace RTDB errado.

## Roteiro manual (feito no navegador)

1. **Motorista** (`motorista1@example.test`):
   - o login leva para `/conta/motorista`;
   - mostra "Ônibus atual: bus1" e a rota "Centro - Rodoviária" com 2 paradas;
   - "Iniciar envio de GPS", com o GPS simulado devolvendo velocidade `NaN` e direção `null`, mostra "Posição enviada";
   - o nó `/telemetry/bus1` foi atualizado no namespace `loirinha-1a25f-default-rtdb`.
2. **Dono** (`dono@example.test`):
   - lista os ônibus HPX-9876 (em uso por DRV001) e DEF-5678 (livre), os motoristas DRV001, DRV002 e DRV003 (inativo) e a rota da frota;
   - "Ver rota em andamento" mostra a rota do bus1;
   - "Atribuir rota" no DRV002 mostra "Rota atribuída.";
   - "Cadastrar rota" com uma parada mostra "Rota cadastrada." e a rota nova aparece na lista;
   - o mapa ao vivo mostra o bus1.
3. **Passageiro** (`passageiro@example.test`):
   - o login leva para `/conta/perfil`;
   - o mapa ao vivo mostra o HPX-9876;
   - depois de 45 s sem envio, o ônibus passa para "Sem sinal".
4. **Celular** (375 px): a tela Conta e a home não têm rolagem lateral.
5. As telas públicas (home, linha, ponto, busca) continuam com os dados simulados.

## Como repetir

```powershell
pnpm typecheck
pnpm test
pnpm build
```

Backend, dentro de `backend/` e pelo Git Bash ou cmd, com `firebase login` feito:

```bash
CHECKIN_E2E=1 FUNCTIONS_DISCOVERY_TIMEOUT=90 firebase emulators:exec --only firestore,auth,functions --project loirinha-1a25f '"functions\venv\Scripts\python.exe" -m pytest functions/tests -q --ignore=functions/tests/fluxo'
```

```bash
firebase emulators:exec --only firestore,database --project loirinha-1a25f '"functions\venv\Scripts\python.exe" -m pytest functions/tests/test_telemetry.py functions/tests/test_telemetry_rules.py -q'
```

Os testes do backend apagam os dados do emulador que estiver rodando. O `emulators:exec` sobe emuladores vazios, então
é seguro. Nunca rode `pytest` direto contra o emulador que tem os seus dados.
