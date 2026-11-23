/** Fluxos de conta. O cliente nunca escolhe claim, papel privilegiado ou frota. */
import {
  createUserWithEmailAndPassword,
  EmailAuthProvider,
  linkWithCredential,
  sendPasswordResetEmail,
  updateProfile,
} from "firebase/auth"
import { httpsCallable } from "firebase/functions"
import { getFirebase } from "../../config/firebase"
import { toBackendError } from "./errors"

export type FleetUser = { id: string; name: string; email: string; active: boolean; routeId?: string }

/** Callables mantêm autorização no servidor e erros de negócio legíveis. */
export async function accountCall<T>(name: string, data: unknown): Promise<T> {
  try {
    return (await httpsCallable<unknown, T>(getFirebase().functions, name)(data)).data
  } catch (error) {
    throw toBackendError(error)
  }
}

/** Reaproveita conta anônima; falha parcial pode ser retomada na tela de conta. */
export async function registerPassenger(name: string, email: string, password: string) {
  const { auth } = getFirebase()
  await auth.authStateReady()
  const result = auth.currentUser?.isAnonymous
    ? await linkWithCredential(auth.currentUser, EmailAuthProvider.credential(email, password))
    : await createUserWithEmailAndPassword(auth, email, password)
  await updateProfile(result.user, { displayName: name.trim() })
  await finishPassenger(name)
}

/** Repetível após falha entre criação de Auth e conclusão do perfil. */
export async function finishPassenger(name: string) {
  await accountCall("registerPassenger", { name: name.trim() })
  await getFirebase().auth.currentUser?.getIdToken(true)
}

/** Resposta da interface é neutra para não revelar se um e-mail possui conta. */
export const resetPassword = (email: string) => sendPasswordResetEmail(getFirebase().auth, email.trim())

/** Mensagens de autenticação não exibem respostas técnicas ou credenciais. */
export function accountError(error: unknown): string {
  const code = (error as { code?: string })?.code
  if (code === "auth/invalid-credential" || code === "auth/wrong-password" || code === "auth/user-not-found")
    return "Confira o e-mail e a senha."
  if (code === "auth/email-already-in-use") return "Este e-mail já possui uma conta. Entre ou recupere a senha."
  if (code === "auth/weak-password") return "Use uma senha com pelo menos 8 caracteres."
  if (code === "auth/too-many-requests") return "Muitas tentativas. Aguarde e tente novamente."
  if (code === "auth/network-request-failed") return "Verifique sua conexão e tente novamente."
  if (code === "auth/invalid-email") return "Informe um e-mail válido."
  if (error instanceof Error && error.name === "BackendError") return error.message
  return "Não foi possível concluir. Confira a conexão e a configuração do serviço."
}
