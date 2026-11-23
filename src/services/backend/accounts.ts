/**
 * Fluxos de conta suportados pelo backend original (backend/, sem alterações):
 * - login com e-mail e senha (auth.ts);
 * - recuperação de senha pelo próprio Firebase Authentication.
 *
 * O backend NÃO tem cadastro de contas: uma conta criada pelo app nasceria sem a claim `role` e sem
 * `users/{uid}`, e nenhuma function a aceitaria (docs/backend/BACKEND.md, seção 5.7 do PDF).
 * As contas são criadas por scripts administrativos (backend/scripts/seed_and_call.py).
 */
import { sendPasswordResetEmail } from "firebase/auth"
import { getFirebase } from "../../config/firebase"

/** A resposta da interface é neutra para não revelar se um e-mail possui conta. */
export const resetPassword = (email: string) => sendPasswordResetEmail(getFirebase().auth, email.trim())

/** Mensagens de autenticação e do backend, sem respostas técnicas ou credenciais. */
export function accountError(error: unknown): string {
  const code = (error as { code?: string })?.code
  if (code === "auth/invalid-credential" || code === "auth/wrong-password" || code === "auth/user-not-found")
    return "Confira o e-mail e a senha."
  if (code === "auth/too-many-requests") return "Muitas tentativas. Aguarde e tente novamente."
  if (code === "auth/network-request-failed") return "Verifique sua conexão e tente novamente."
  if (code === "auth/invalid-email") return "Informe um e-mail válido."
  if (code === "permission-denied") return "Sem permissão para ver estes dados."
  if (error instanceof Error && error.name === "BackendError") return error.message
  if (error instanceof Error && error.message.startsWith("Configure VITE_FIREBASE"))
    return "O acesso ainda não está configurado neste ambiente."
  return "Não foi possível concluir. Confira a conexão e a configuração do serviço."
}
