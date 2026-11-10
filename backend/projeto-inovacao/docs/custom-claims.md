# Custom Claims: papéis de usuário (Firebase Auth)

Guia passo a passo para rodar, testar e integrar o script que atribui papéis (roles) aos usuários do Firebase Authentication.

**Papéis:** `passageiro`, `motorista`, `dono_frota`
**Formato do claim:** sempre `{ "role": "<papel>" }`

---

## 1. O que foi entregue

```text
scripts/firebase/
├── set-custom-claim.js   # atribui/atualiza a role de um usuário
├── get-custom-claim.js   # consulta os claims de um usuário
└── lib/
    ├── roles.js          # ÚNICA lista de roles (ALLOWED_ROLES)
    ├── env.js            # validação de ambiente (emulador x produção)
    ├── admin.js          # inicialização do Firebase Admin SDK
    └── claims.js         # setUserRole / getUserClaims (reutilizável, ex.: Cloud Functions)
firebase.json             # configuração do Auth Emulator (porta 9099, UI 4000)
.env.example              # modelo de variáveis (o .env real NÃO vai para o Git)
.gitignore                # bloqueia .env e arquivos de Service Account
package.json              # dependências e atalhos (npm run ...)
test/                     # testes unitários + teste ponta a ponta no emulador
```

O que o script garante:

- só aceita as 3 roles permitidas; qualquer outra é rejeitada;
- UID inexistente gera erro claro, sem quebrar;
- **preserva** outros claims do usuário (só o campo `role` muda);
- nenhuma credencial no código; por padrão roda **apenas no emulador**.

---

## 2. Pré-requisitos

- **Node.js 20.12 ou superior** (`node -v` para conferir).
- **Java não é necessário** (o Auth Emulator não usa).
- Acesso ao repositório.

---

## 3. Passo a passo: rodar localmente (emulador)

### Passo 1: instalar dependências

```bash
npm install
```

### Passo 2: criar o arquivo de ambiente

```bash
cp .env.example .env
```

O `.env.example` já vem configurado para o emulador. Não precisa editar nada:

```text
APP_ENV=emulator
FIREBASE_PROJECT_ID=demo-loirinha
FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099
```

### Passo 3: subir o emulador (terminal 1)

```bash
npm run emulators
```

Deixe esse terminal aberto. Use sempre esse comando, e não `firebase emulators:start` direto: ele fixa o projeto `demo-loirinha`, o mesmo que o script usa. Se o projeto for diferente, o script não encontra os usuários.

Painel do emulador: http://127.0.0.1:4000

### Passo 4: criar um usuário de teste

1. Abra http://127.0.0.1:4000 e entre na aba **Authentication**.
2. Clique em **Add user** e informe qualquer e-mail e senha.
3. Copie o valor da coluna **User UID** (algo como `rpdGnaWSxcWbHyCIUEH091ymFuAp`).

> Os usuários do emulador **são apagados quando ele é parado**. Ao reiniciar, crie o usuário de novo.

### Passo 5: atribuir a role (terminal 2)

Troque `abc123XYZ` pelo UID copiado:

```bash
node scripts/firebase/set-custom-claim.js abc123XYZ passageiro
node scripts/firebase/set-custom-claim.js abc123XYZ motorista
node scripts/firebase/set-custom-claim.js abc123XYZ dono_frota
```

> Digite o UID **sem** os sinais `< >`. No terminal (zsh/bash) eles são redirecionamento de arquivo e geram `no such file or directory`.

Saída esperada:

```text
Ambiente: emulator | projeto: demo-loirinha
Usuário encontrado: abc123XYZ
Role atualizada com sucesso.
Role: motorista (anterior: passageiro)
Obs.: o usuário precisa renovar o ID Token para receber o novo claim.
```

Para **alterar** a role, rode o mesmo comando com outra role. Só o campo `role` muda.

### Passo 6: verificar o resultado

```bash
node scripts/firebase/get-custom-claim.js abc123XYZ
```

```text
Custom claims de abc123XYZ:
{
  "role": "motorista"
}
```

### Passo 7: rodar os testes

```bash
npm test                                   # unitários (não precisam do emulador)
npx firebase emulators:exec --only auth --project demo-loirinha "bash test/e2e-emulator.sh"
```

O segundo comando sobe o emulador sozinho, testa as 3 roles, role inválida, UID inexistente e preservação de claims, e depois o desliga.

---

## 4. Erros comuns

| Mensagem | Causa e solução |
|---|---|
| `zsh: no such file or directory: UID` | Você digitou `<UID>` com os sinais. Use só o valor, sem `< >`. |
| `Erro: usuário não encontrado no Firebase Authentication.` | UID digitado errado (cuidado com `0`/`O` e `I`/`l`), usuário criado antes de reiniciar o emulador, ou emulador iniciado com outro projeto. Suba com `npm run emulators` e recrie o usuário. |
| `Erro: role inválida.` | A role não está na lista. Use `passageiro`, `motorista` ou `dono_frota`. |
| `Erro: APP_ENV=emulator exige FIREBASE_AUTH_EMULATOR_HOST` | Falta o `.env`. Rode `cp .env.example .env`. |
| `falha inesperada: ... ECONNREFUSED` | O emulador não está rodando. Suba com `npm run emulators`. |

---

## 5. Produção (uso excepcional)

Por padrão o script **nunca** toca em produção. Para usar no projeto real:

1. Quem administra o Firebase gera a Service Account: Console → Configurações do projeto → Contas de serviço → *Gerar nova chave privada*.
2. Guarde o JSON **fora do repositório** e passe-o ao time por um canal seguro (nunca pelo Git, e-mail ou chat aberto).
3. Defina as variáveis (exportadas no terminal ou em um `.env` local):

   | Variável | Valor em produção |
   |---|---|
   | `APP_ENV` | `production` |
   | `FIREBASE_PROJECT_ID` | ID real do projeto |
   | `GOOGLE_APPLICATION_CREDENTIALS` | caminho do JSON da Service Account |
   | `FIREBASE_AUTH_EMULATOR_HOST` | **remover** (é proibida em produção) |

4. Rode com a confirmação explícita:

   ```bash
   node scripts/firebase/set-custom-claim.js abc123XYZ motorista --confirm-production
   ```

### Proteções contra acidentes

- Padrão é sempre emulador; produção exige `APP_ENV=production` **e** `--confirm-production`.
- Emulador: o projeto deve começar com `demo-` e o host do emulador deve estar definido, então não alcança um projeto real.
- Produção: recusa projeto `demo-*`, recusa se houver host de emulador definido e exige credenciais.

---

## 6. Para o time Flutter: como ler a role

```text
Usuário faz login
      ↓
Firebase Authentication
      ↓
ID Token (JWT)
      ↓
Custom Claims
      ↓
role: passageiro | motorista | dono_frota
      ↓
Flutter identifica as permissões do usuário
```

```dart
import 'package:firebase_auth/firebase_auth.dart';

enum AppRole { passageiro, motorista, donoFrota }

Future<AppRole?> currentRole({bool forceRefresh = false}) async {
  final user = FirebaseAuth.instance.currentUser;
  if (user == null) return null;
  final result = await user.getIdTokenResult(forceRefresh); // true => busca token novo
  switch (result.claims?['role']) {
    case 'passageiro':  return AppRole.passageiro;
    case 'motorista':   return AppRole.motorista;
    case 'dono_frota':  return AppRole.donoFrota;
    default:            return null; // usuário sem role atribuída
  }
}
```

### Renovação do token

Os claims ficam **dentro do ID Token**, que dura até 1 hora. Depois de mudar uma role, o app só vê o valor novo quando o token for renovado:

- `getIdTokenResult(true)` ou `getIdToken(true)` força a renovação (ex.: logo após o login ou ao abrir o app);
- ou o usuário faz logout e login novamente.

### Pontos de atenção

- Usuário recém-criado **não tem role** (`null`). O app deve tratar esse caso (ex.: tela de espera).
- Esconder telas no Flutter só melhora a experiência; **quem protege os dados é o servidor**. Use `request.auth.token.role` nas Security Rules e `context.auth.token.role` em Cloud Functions.
- Em desenvolvimento, aponte o app para o emulador: `FirebaseAuth.instance.useAuthEmulator('localhost', 9099)` (no Android Emulator use `10.0.2.2` no lugar de `localhost`).

---

## 7. Limites e boas práticas

- Custom Claims servem **somente para autorização/permissão**. O limite total é de **1000 bytes**; não guarde dados de negócio, perfil, listas ou preferências (use o Firestore).
- `setCustomUserClaims` substitui todos os claims; por isso o script faz *merge* com os existentes.
- Atribuir roles é uma operação privilegiada: só no backend/script com Admin SDK, nunca a partir de dados enviados pelo cliente.

---

## 8. Adicionar novas roles no futuro

1. Inclua o nome em `ALLOWED_ROLES`, em `scripts/firebase/lib/roles.js`. CLI, validação e mensagens se ajustam sozinhos.
2. Atualize as Security Rules e o `enum` do Flutter.
3. Adicione um caso nos testes (`test/custom-claims.test.js`).

---

## 9. Checklist do que o outro dev precisa fazer

- [ ] `npm install` e `cp .env.example .env`
- [ ] Subir o emulador com `npm run emulators` e criar um usuário de teste
- [ ] Atribuir as 3 roles e conferir com `get-custom-claim.js`
- [ ] Rodar `npm test` e o teste ponta a ponta
- [ ] (Produção) Gerar a Service Account e guardá-la fora do repositório
- [ ] Escrever as Security Rules usando `request.auth.token.role`
- [ ] (Flutter) Integrar `currentRole()` e tratar usuário sem role
