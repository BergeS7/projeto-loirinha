/** Indicador compartilhado: nunca apresenta falhas ou respostas antigas como tempo real. */
import { useEffect, useState } from "react"
import useOnlineStatus from "../../hooks/useOnlineStatus"

type Props = {
  error?: unknown
  loading: boolean
  updatedAt?: number
  onRetry: () => void
  maxAgeMs?: number
}

export default function DataStatus({ error, loading, updatedAt, onRetry, maxAgeMs = 45_000 }: Props) {
  const online = useOnlineStatus()
  const [now, setNow] = useState(Date.now)
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 5000)
    return () => window.clearInterval(timer)
  }, [])
  const stale = updatedAt !== undefined && now - updatedAt > maxAgeMs
  const failed = error !== undefined || !online || stale
  return (
    <div className={`data-status ${failed ? "data-status-warning" : ""}`} role="status">
      <span>
        {loading
          ? "Carregando dados…"
          : failed
            ? "Atualização indisponível. Os dados podem estar desatualizados."
            : "Dados atualizados"}
      </span>
      {failed && (
        <button type="button" className="secondary-button" onClick={onRetry}>
          Tentar de novo
        </button>
      )}
    </div>
  )
}
