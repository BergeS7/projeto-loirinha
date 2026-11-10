#!/usr/bin/env bash
# Teste ponta a ponta contra o Auth Emulator.
# Uso: npx firebase emulators:exec --only auth --project demo-loirinha "bash test/e2e-emulator.sh"
set -u
export APP_ENV=emulator FIREBASE_PROJECT_ID=demo-loirinha
HOST="${FIREBASE_AUTH_EMULATOR_HOST:-127.0.0.1:9099}"; export FIREBASE_AUTH_EMULATOR_HOST="$HOST"

# Cria usuario com um claim pre-existente (para provar que ele e preservado)
UID_NEW=$(node -e "
const a=require('firebase-admin');a.initializeApp({projectId:'demo-loirinha'});
a.auth().createUser({email:'teste@loirinha.dev'}).then(async u=>{await a.auth().setCustomUserClaims(u.uid,{beta:true});console.log(u.uid)})")

fail=0
for r in passageiro motorista dono_frota; do
  node scripts/firebase/set-custom-claim.js "$UID_NEW" "$r" >/dev/null || { echo "FALHA: $r"; fail=1; }
  node scripts/firebase/get-custom-claim.js "$UID_NEW" | tr -d ' \n' | grep -q "\"role\":\"$r\"" && echo "OK  role=$r" || { echo "FALHA verificar $r"; fail=1; }
done
node scripts/firebase/get-custom-claim.js "$UID_NEW" | grep -q '"beta": true' && echo "OK  claim 'beta' preservado" || { echo "FALHA: beta perdido"; fail=1; }
node scripts/firebase/set-custom-claim.js "$UID_NEW" admin 2>&1 | grep -q "role inválida" && echo "OK  role invalida rejeitada" || { echo "FALHA role invalida"; fail=1; }
node scripts/firebase/set-custom-claim.js uid-inexistente motorista 2>&1 | grep -q "usuário não encontrado" && echo "OK  UID inexistente tratado" || { echo "FALHA uid"; fail=1; }
exit $fail
