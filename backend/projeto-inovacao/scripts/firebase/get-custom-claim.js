#!/usr/bin/env node
'use strict';

/** Uso: node scripts/firebase/get-custom-claim.js <UID> [--confirm-production] */
const { loadDotEnv, resolveConfig, ConfigError } = require('./lib/env');
const { initAdmin } = require('./lib/admin');
const { getUserClaims, UserNotFoundError } = require('./lib/claims');

function fail(message) {
  console.error(`Erro: ${message}`);
  process.exit(1);
}

async function main() {
  const args = process.argv.slice(2);
  const [uid] = args.filter((a) => !a.startsWith('--'));
  if (!uid) fail('uso: node scripts/firebase/get-custom-claim.js UID_DO_USUARIO [--confirm-production]');

  loadDotEnv();
  const config = resolveConfig({ confirmProduction: args.includes('--confirm-production') });
  const claims = await getUserClaims(initAdmin(config).auth(), uid);
  console.log(`Custom claims de ${uid}:`);
  console.log(JSON.stringify(claims, null, 2));
}

main().catch((err) => {
  if (err instanceof UserNotFoundError) fail('usuário não encontrado no Firebase Authentication.');
  if (err instanceof ConfigError) fail(err.message);
  fail(`falha inesperada: ${err.message}`);
});
