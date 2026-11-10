'use strict';

const admin = require('firebase-admin');
const { ENVIRONMENTS } = require('./env');

/** Inicializa o Admin SDK (idempotente). Nenhuma credencial fica no codigo. */
function initAdmin({ appEnv, projectId }) {
  if (admin.apps.length) return admin.app();
  if (appEnv === ENVIRONMENTS.EMULATOR) {
    // O SDK le FIREBASE_AUTH_EMULATOR_HOST do ambiente; nao precisa de credenciais.
    return admin.initializeApp({ projectId });
  }
  // Producao: Service Account via GOOGLE_APPLICATION_CREDENTIALS (caminho do arquivo).
  return admin.initializeApp({ projectId, credential: admin.credential.applicationDefault() });
}

module.exports = { initAdmin };
