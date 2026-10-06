/** Acesso ao localStorage que não quebra em modo privado ou com o armazenamento bloqueado. */
export function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw === null ? fallback : (JSON.parse(raw) as T)
  } catch {
    return fallback
  }
}

/**
 * Salva um valor como JSON no localStorage. Se o armazenamento estiver cheio ou bloqueado, ignora
 * sem quebrar o app.
 */
export function writeJson(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Armazenamento cheio ou bloqueado: a preferência só não persiste.
  }
}
