'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { setUserRole, getUserClaims, UserNotFoundError, InvalidRoleError } = require('../scripts/firebase/lib/claims');
const { resolveConfig, ConfigError } = require('../scripts/firebase/lib/env');

function fakeAuth(users) {
  return {
    async getUser(uid) {
      if (!users[uid]) throw Object.assign(new Error('nf'), { code: 'auth/user-not-found' });
      return { uid, customClaims: users[uid] };
    },
    async setCustomUserClaims(uid, claims) {
      users[uid] = claims;
    },
  };
}

test('atribui cada role permitida', async () => {
  for (const role of ['passageiro', 'motorista', 'dono_frota']) {
    const users = { u1: undefined };
    users.u1 = {};
    const r = await setUserRole(fakeAuth(users), 'u1', role);
    assert.equal(r.role, role);
    assert.deepEqual(users.u1, { role });
  }
});

test('rejeita role inválida sem consultar o Auth', async () => {
  await assert.rejects(setUserRole(fakeAuth({}), 'u1', 'admin'), InvalidRoleError);
  await assert.rejects(setUserRole(fakeAuth({}), 'u1', undefined), InvalidRoleError);
});

test('UID inexistente gera erro tratado', async () => {
  await assert.rejects(setUserRole(fakeAuth({}), 'nope', 'motorista'), UserNotFoundError);
  await assert.rejects(getUserClaims(fakeAuth({}), 'nope'), UserNotFoundError);
});

test('preserva claims existentes e registra role anterior', async () => {
  const users = { u1: { role: 'passageiro', beta: true } };
  const r = await setUserRole(fakeAuth(users), 'u1', 'motorista');
  assert.equal(r.previousRole, 'passageiro');
  assert.deepEqual(users.u1, { role: 'motorista', beta: true });
});

test('config: emulador exige host e projectId demo-*', () => {
  assert.throws(() => resolveConfig({ env: { FIREBASE_PROJECT_ID: 'demo-x' } }), ConfigError);
  assert.throws(
    () => resolveConfig({ env: { FIREBASE_PROJECT_ID: 'real-prod', FIREBASE_AUTH_EMULATOR_HOST: 'h:1' } }),
    ConfigError
  );
  assert.equal(
    resolveConfig({ env: { FIREBASE_PROJECT_ID: 'demo-x', FIREBASE_AUTH_EMULATOR_HOST: 'h:1' } }).appEnv,
    'emulator'
  );
});

test('config: producao exige confirmacao, credenciais e ausencia de emulador', () => {
  const base = { APP_ENV: 'production', FIREBASE_PROJECT_ID: 'loirinha-prod', GOOGLE_APPLICATION_CREDENTIALS: '/x.json' };
  assert.throws(() => resolveConfig({ env: base }), /confirm-production/);
  assert.throws(() => resolveConfig({ env: { ...base, FIREBASE_AUTH_EMULATOR_HOST: 'h:1' }, confirmProduction: true }), ConfigError);
  assert.throws(() => resolveConfig({ env: { ...base, GOOGLE_APPLICATION_CREDENTIALS: '' }, confirmProduction: true }), ConfigError);
  assert.throws(() => resolveConfig({ env: { ...base, FIREBASE_PROJECT_ID: 'demo-x' }, confirmProduction: true }), ConfigError);
  assert.equal(resolveConfig({ env: base, confirmProduction: true }).appEnv, 'production');
});
