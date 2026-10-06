/** Preferências do usuário guardadas no aparelho (localStorage): favoritos e buscas recentes. */
import { BUSCAS_RECENTES_LIMITE, STORAGE_KEYS } from "../config/constants"
import { readJson, writeJson } from "../lib/storage"

/**
 * Ids das linhas e dos pontos favoritados.
 * Quando houver login, os favoritos podem ser sincronizados com o backend a partir daqui.
 */
export type Favoritos = { linhas: string[]; pontos: string[] }
/** Tipo de item favoritado: linha ou ponto. */
export type TipoFavorito = keyof Favoritos

/** Evento disparado na janela quando os favoritos mudam, para todas as telas abertas se atualizarem. */
export const FAVORITOS_EVENT = "loirinha:favorites-changed"

/** Favoritos salvos no aparelho. */
export function getFavoritos(): Favoritos {
  const salvo = readJson<Partial<Favoritos>>(STORAGE_KEYS.favoritos, {})
  return { linhas: salvo.linhas ?? [], pontos: salvo.pontos ?? [] }
}

/** Adiciona o item aos favoritos, ou remove se já estiver lá. Devolve os favoritos atualizados. */
export function alternarFavorito(tipo: TipoFavorito, id: string): Favoritos {
  const atual = getFavoritos()
  const lista = atual[tipo]
  const atualizado = { ...atual, [tipo]: lista.includes(id) ? lista.filter((item) => item !== id) : [...lista, id] }
  writeJson(STORAGE_KEYS.favoritos, atualizado)
  window.dispatchEvent(new Event(FAVORITOS_EVENT))
  return atualizado
}

/** Últimas buscas feitas, da mais recente para a mais antiga. */
export function getBuscasRecentes(): string[] {
  return readJson<string[]>(STORAGE_KEYS.buscasRecentes, [])
}

/** Guarda a busca no topo das recentes (sem repetir) e devolve a lista atualizada. */
export function salvarBuscaRecente(termo: string): string[] {
  const valor = termo.trim()
  if (!valor) return getBuscasRecentes()
  const recentes = [valor, ...getBuscasRecentes().filter((item) => item !== valor)].slice(0, BUSCAS_RECENTES_LIMITE)
  writeJson(STORAGE_KEYS.buscasRecentes, recentes)
  return recentes
}
