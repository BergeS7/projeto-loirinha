/**
 * Login no Firebase Authentication. O papel vem da custom claim `role` do token (nunca de
 * `users.role`). O cadastro de contas ainda não existe no backend: use as contas de teste do
 * emulador (docs/backend/BACKEND.md, seção 4).
 */
import { onAuthStateChanged, signInWithEmailAndPassword, signOut as firebaseSignOut, type User } from "firebase/auth"
import { getFirebase } from "../../config/firebase"
import type { Role } from "../../types/backend"

const ROLES: readonly Role[] = ["dono_frota", "motorista", "passageiro"]

export function signIn(email: string, password: string) {
  return signInWithEmailAndPassword(getFirebase().auth, email, password)
}

export function signOut() {
  return firebaseSignOut(getFirebase().auth)
}

/** Observa o usuário logado. Devolve a função para parar de observar. */
export function onUserChanged(callback: (user: User | null) => void) {
  return onAuthStateChanged(getFirebase().auth, callback)
}

/**
 * Papel do usuário logado, lido do token. `forceRefresh` pega um token novo (necessário depois de
 * uma mudança de papel, já que o token antigo vale ~1 h com o papel antigo).
 */
export async function getRole(forceRefresh = false): Promise<Role | null> {
  const user = getFirebase().auth.currentUser
  if (!user) return null
  const { claims } = await user.getIdTokenResult(forceRefresh)
  const role = claims.role
  return typeof role === "string" && (ROLES as readonly string[]).includes(role) ? (role as Role) : null
}
