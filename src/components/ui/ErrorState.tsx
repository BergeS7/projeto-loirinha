import { RefreshCw, WifiOff } from "lucide-react"
import { NetworkError } from "../../lib/http"
import EmptyState from "./EmptyState"

type Props = {
  error?: unknown
  title?: string
  onRetry?: () => void
}

export default function ErrorState({ error, title = "Não foi possível carregar", onRetry }: Props) {
  const offline = error instanceof NetworkError || !navigator.onLine
  const description = offline ? "Verifique sua conexão e tente novamente." : "Tente novamente em alguns instantes."

  return (
    <EmptyState icon={offline ? <WifiOff size={30} /> : undefined} title={title} description={description}>
      {onRetry && (
        <button type="button" className="secondary-button" onClick={onRetry}>
          <RefreshCw size={18} /> Tentar de novo
        </button>
      )}
    </EmptyState>
  )
}
