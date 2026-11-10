/**
 * Tradução dos erros do backend. O campo estável é `details.reason`; a `message` do servidor pode
 * mudar. Catálogo: docs/backend/BACKEND.md, seção 3 (seção 4.13 do PDF).
 */
import { FirebaseError } from "firebase/app"

/** Mensagem para o usuário, por `reason`. */
const MENSAGENS: Record<string, string> = {
  unauthenticated: "Sua sessão expirou. Entre de novo.",
  missing_role_claim: "Sua conta ainda não tem um perfil definido.",
  invalid_role: "Sua conta tem um perfil inválido.",
  not_a_driver: "Esta ação é só para motoristas.",
  not_a_fleet_owner: "Esta ação é só para donos de frota.",
  user_not_found: "Usuário não encontrado.",
  driver_record_not_found: "Motorista sem cadastro.",
  duplicate_driver_record: "Cadastro de motorista duplicado. Fale com o dono da frota.",
  driver_inactive: "Seu cadastro de motorista está inativo.",
  fleet_mismatch_driver_user: "Seu cadastro está ligado a outra frota.",
  bus_not_found: "Nenhum ônibus encontrado com essa tag.",
  duplicate_tag_code: "Essa tag está em mais de um ônibus. Fale com o dono da frota.",
  bus_other_fleet: "Este ônibus pertence a outra frota.",
  bus_occupied: "Este ônibus já está com outro motorista.",
  already_checked_in_here: "Você já está com este ônibus.",
  not_active_driver: "Você não fez check-in neste ônibus.",
  no_active_driver: "Este ônibus está sem motorista.",
  driver_without_route: "O motorista ainda não tem rota atribuída.",
  driver_not_found: "Motorista não encontrado.",
  driver_other_fleet: "Este motorista é de outra frota.",
  route_not_found: "Rota não encontrada.",
  route_without_fleet: "Esta rota não pertence a nenhuma frota.",
  route_other_fleet: "Esta rota é de outra frota.",
  fleet_not_owned: "Sua conta não é dona de uma frota.",
  invalid_tag_code: "Informe a tag do ônibus.",
  invalid_route: "Confira os dados da rota.",
  stale_fix: "Posição antiga descartada.",
  stale_update: "Posição repetida descartada.",
  captured_at_in_future: "O relógio do aparelho está errado.",
  null_island: "O GPS ainda não encontrou a posição.",
  contention: "Muita gente usando agora. Tente de novo.",
}

const GENERICA = "Não foi possível concluir. Tente de novo."

/** Erro de uma chamada ao backend, com o `reason` estável e uma mensagem amigável. */
export class BackendError extends Error {
  /** Código do Firebase sem o prefixo, ex.: "permission-denied". */
  readonly code: string
  /** `details.reason` do backend, ex.: "bus_occupied". Vazio quando o erro não veio do backend. */
  readonly reason: string

  constructor(code: string, reason: string, message: string, options?: { cause?: unknown }) {
    super(message, options)
    this.name = "BackendError"
    this.code = code
    this.reason = reason
  }

  /** O usuário precisa entrar de novo. */
  get precisaLogin() {
    return this.code === "unauthenticated"
  }
}

/** Converte qualquer erro de uma chamada em BackendError. */
export function toBackendError(error: unknown): BackendError {
  if (error instanceof BackendError) return error
  if (error instanceof FirebaseError) {
    const code = error.code.replace(/^functions\//, "")
    const details = (error as FirebaseError & { details?: unknown }).details
    const reason =
      details && typeof details === "object" && "reason" in details ? String((details as { reason: unknown }).reason) : ""
    const chave = reason || code
    const mensagem = MENSAGENS[chave] ?? (chave.startsWith("invalid_") ? "Dados inválidos." : GENERICA)
    return new BackendError(code, reason, mensagem, { cause: error })
  }
  return new BackendError("unknown", "", GENERICA, { cause: error })
}
