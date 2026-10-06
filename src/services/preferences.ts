import { BUSCAS_RECENTES_LIMITE, STORAGE_KEYS } from "../config/constants"
import { readJson, writeJson } from "../lib/storage"

/**
 * Preferências guardadas só no aparelho.
 * Quando houver login, favoritos podem ser sincronizados com o backend a partir daqui.
 */
export type Favoritos = { linhas: string[]; pontos: string[] }
export type TipoFavorito = keyof Favoritos

export const FAVORITOS_EVENT = "loirinha:favorites-changed"

export function getFavoritos(): Favoritos {
  const salvo = readJson<Partial<Favoritos>>(STORAGE_KEYS.favoritos, {})
  return { linhas: salvo.linhas ?? [], pontos: salvo.pontos ?? [] }
}

export function alternarFavorito(tipo: TipoFavorito, id: string): Favoritos {
  const atual = getFavoritos()
  const lista = atual[tipo]
  const atualizado = { ...atual, [tipo]: lista.includes(id) ? lista.filter((item) => item !== id) : [...lista, id] }
  writeJson(STORAGE_KEYS.favoritos, atualizado)
  window.dispatchEvent(new Event(FAVORITOS_EVENT))
  return atualizado
}

export function getBuscasRecentes(): string[] {
  return readJson<string[]>(STORAGE_KEYS.buscasRecentes, [])
}

export function salvarBuscaRecente(termo: string): string[] {
  const valor = termo.trim()
  if (!valor) return getBuscasRecentes()
  const recentes = [valor, ...getBuscasRecentes().filter((item) => item !== valor)].slice(0, BUSCAS_RECENTES_LIMITE)
  writeJson(STORAGE_KEYS.buscasRecentes, recentes)
  return recentes
}
