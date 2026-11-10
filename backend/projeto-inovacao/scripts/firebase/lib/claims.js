'use strict';

const { ROLE_CLAIM_KEY, ALLOWED_ROLES, isValidRole } = require('./roles');

class UserNotFoundError extends Error {}
class InvalidRoleError extends Error {
  constructor(role) {
    super(`role inválida${role ? ` ("${role}")` : ''}.\nRoles permitidas: ${ALLOWED_ROLES.join(', ')}`);
  }
}

/**
 * Define a role do usuario preservando os demais custom claims.
 * (setCustomUserClaims SUBSTITUI todos os claims, por isso fazemos o merge.)
 * @param {import('firebase-admin').auth.Auth} auth
 */
async function setUserRole(auth, uid, role) {
  if (!isValidRole(role)) throw new InvalidRoleError(role);

  let user;
  try {
    user = await auth.getUser(uid);
  } catch (err) {
    if (err.code === 'auth/user-not-found') throw new UserNotFoundError(uid);
    throw err;
  }

  const previousRole = user.customClaims?.[ROLE_CLAIM_KEY];
  const claims = { ...(user.customClaims ?? {}), [ROLE_CLAIM_KEY]: role };
  await auth.setCustomUserClaims(uid, claims);
  return { uid, previousRole, role, claims };
}

async function getUserClaims(auth, uid) {
  try {
    const user = await auth.getUser(uid);
    return user.customClaims ?? {};
  } catch (err) {
    if (err.code === 'auth/user-not-found') throw new UserNotFoundError(uid);
    throw err;
  }
}

module.exports = { setUserRole, getUserClaims, UserNotFoundError, InvalidRoleError };
