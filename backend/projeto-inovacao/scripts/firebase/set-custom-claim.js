#!/usr/bin/env node
'use strict';

/**
 * Uso: node scripts/firebase/set-custom-claim.js <UID> <role> [--confirm-production]
 * Roles: passageiro | motorista | dono_frota
 */
const { ALLOWED_ROLES, isValidRole } = require('./lib/roles');
const { loadDotEnv, resolveConfig, ConfigError } = require('./lib/env');
const { initAdmin } = require('./lib/admin');
const { setUserRole, UserNotFoundError } = require('./lib/claims');

function fail(message, code = 1) {
  console.error(`Erro: ${message}`);
  process.exit(code);
}

async function main() {
  const args = process.argv.slice(2);
  const confirmProduction = args.includes('--confirm-production');
  const [uid, role] = args.filter((a) => !a.startsWith('--'));

  if (!uid || !role) {
    fail(`uso: node scripts/firebase/set-custom-claim.js UID_DO_USUARIO ROLE [--confirm-production]\nRoles permitidas: ${ALLOWED_ROLES.join(', ')}`);
  }
  if (!isValidRole(role)) {
    fail(`role inválida.\nRoles permitidas: ${ALLOWED_ROLES.join(', ')}`);
  }

  loadDotEnv();
  const config = resolveConfig({ confirmProduction });
  console.log(`Ambiente: ${config.appEnv} | projeto: ${config.projectId}`);

  const auth = initAdmin(config).auth();
  const result = await setUserRole(auth, uid, role);

  console.log(`Usuário encontrado: ${uid}`);
  console.log('Role atualizada com sucesso.');
  console.log(`Role: ${result.role}${result.previousRole ? ` (anterior: ${result.previousRole})` : ''}`);
  console.log('Obs.: o usuário precisa renovar o ID Token para receber o novo claim.');
}

main().catch((err) => {
  if (err instanceof UserNotFoundError) fail('usuário não encontrado no Firebase Authentication.');
  if (err instanceof ConfigError) fail(err.message);
  fail(`falha inesperada: ${err.message}`);
});
