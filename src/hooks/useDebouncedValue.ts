/** Hook de debounce: atrasa a atualização de um valor até ele parar de mudar. */
import { useEffect, useState } from "react"

/**
 * Devolve `value` só depois de ele ficar `delayMs` sem mudar. Usado na busca para esperar o usuário
 * parar de digitar.
 */
export default function useDebouncedValue<T>(value: T, delayMs: number) {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}
