'use strict';

/**
 * Fonte unica das roles do sistema.
 * Para adicionar uma role futura (ex.: admin, suporte), basta incluir aqui.
 */
const ROLE_CLAIM_KEY = 'role';

const ALLOWED_ROLES = Object.freeze(['passageiro', 'motorista', 'dono_frota']);

function isValidRole(role) {
  return typeof role === 'string' && ALLOWED_ROLES.includes(role);
}

module.exports = { ROLE_CLAIM_KEY, ALLOWED_ROLES, isValidRole };
