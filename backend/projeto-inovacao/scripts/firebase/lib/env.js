'use strict';

const fs = require('node:fs');
const path = require('node:path');

const ENVIRONMENTS = Object.freeze({ EMULATOR: 'emulator', PRODUCTION: 'production' });

/** Carrega .env da raiz do projeto, se existir (variaveis ja exportadas tem prioridade). */
function loadDotEnv() {
  const file = path.resolve(__dirname, '../../../.env');
  if (fs.existsSync(file)) process.loadEnvFile(file);
}

class ConfigError extends Error {}

/**
 * Valida a configuracao e devolve { appEnv, projectId, emulatorHost }.
 * Regras de seguranca:
 *  - Padrao e SEMPRE emulador.
 *  - emulator: exige FIREBASE_AUTH_EMULATOR_HOST e projectId "demo-*".
 *  - production: exige APP_ENV=production explicito, projectId real (nao "demo-*"),
 *    credenciais, NENHUM emulador configurado e a flag --confirm-production.
 */
function resolveConfig({ env = process.env, confirmProduction = false } = {}) {
  const appEnv = env.APP_ENV || ENVIRONMENTS.EMULATOR;
  const projectId = env.FIREBASE_PROJECT_ID;
  const emulatorHost = env.FIREBASE_AUTH_EMULATOR_HOST;

  if (!Object.values(ENVIRONMENTS).includes(appEnv)) {
    throw new ConfigError(`APP_ENV invalido: "${appEnv}". Use "emulator" ou "production".`);
  }
  if (!projectId) {
    throw new ConfigError('FIREBASE_PROJECT_ID nao definido (veja .env.example).');
  }

  if (appEnv === ENVIRONMENTS.EMULATOR) {
    if (!emulatorHost) {
      throw new ConfigError('APP_ENV=emulator exige FIREBASE_AUTH_EMULATOR_HOST (ex.: 127.0.0.1:9099).');
    }
    if (!projectId.startsWith('demo-')) {
      throw new ConfigError(
        `Em modo emulador o FIREBASE_PROJECT_ID deve comecar com "demo-" (recebido: "${projectId}").`
      );
    }
    return { appEnv, projectId, emulatorHost };
  }

  // production
  if (emulatorHost) {
    throw new ConfigError('FIREBASE_AUTH_EMULATOR_HOST esta definido, mas APP_ENV=production. Remova-o.');
  }
  if (projectId.startsWith('demo-')) {
    throw new ConfigError(`FIREBASE_PROJECT_ID "${projectId}" e de emulador; produção exige o ID real.`);
  }
  if (!env.GOOGLE_APPLICATION_CREDENTIALS) {
    throw new ConfigError('Producao exige GOOGLE_APPLICATION_CREDENTIALS apontando para o JSON da Service Account.');
  }
  if (!confirmProduction) {
    throw new ConfigError(`Operacao em PRODUCAO (${projectId}). Repita com --confirm-production para confirmar.`);
  }
  return { appEnv, projectId, emulatorHost: undefined };
}

module.exports = { ENVIRONMENTS, ConfigError, loadDotEnv, resolveConfig };
