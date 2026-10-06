import { type DependencyList, useCallback, useEffect, useRef, useState } from "react"

export type Loader<T> = (signal: AbortSignal) => Promise<T>

export type AsyncData<T> = {
  data: T | undefined
  error: unknown
  /** Verdadeiro só enquanto ainda não há dados para mostrar. */
  loading: boolean
  reload: () => void
}

type Options = {
  /** Recarrega em segundo plano a cada N ms, mantendo os dados atuais na tela. */
  refreshInterval?: number
}

/**
 * Carrega dados assíncronos com cancelamento, tratamento de erro e atualização periódica.
 * Passe `null` como loader para não carregar nada (ex.: busca vazia).
 * Quando `deps` mudam, os dados anteriores são descartados e a carga recomeça.
 */
export default function useAsyncData<T>(loader: Loader<T> | null, deps: DependencyList, options: Options = {}): AsyncData<T> {
  const { refreshInterval } = options
  const enabled = loader !== null
  const [state, setState] = useState<Omit<AsyncData<T>, "reload">>({ data: undefined, error: undefined, loading: enabled })
  const loaderRef = useRef(loader)
  const runRef = useRef<() => void>(() => {})

  useEffect(() => {
    loaderRef.current = loader
  })

  useEffect(() => {
    setState({ data: undefined, error: undefined, loading: enabled })
    if (!enabled) return

    let controller: AbortController | undefined
    const run = async () => {
      controller?.abort()
      const current = new AbortController()
      controller = current
      setState((prev) => (prev.data === undefined ? { ...prev, loading: true, error: undefined } : prev))

      try {
        const data = await loaderRef.current!(current.signal)
        if (!current.signal.aborted) setState({ data, error: undefined, loading: false })
      } catch (error) {
        if (!current.signal.aborted) setState((prev) => ({ data: prev.data, error, loading: false }))
      }
    }

    runRef.current = run
    run()
    const timer = refreshInterval ? window.setInterval(run, refreshInterval) : undefined

    return () => {
      controller?.abort()
      window.clearInterval(timer)
    }
    // `deps` vem de quem chama, como em useEffect.
  }, [enabled, refreshInterval, ...deps])

  const reload = useCallback(() => runRef.current(), [])
  return { ...state, reload }
}
