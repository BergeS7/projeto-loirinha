/** Tela de avisos (/avisos): atrasos, desvios e informações da operação. */
import { AlertTriangle, Bell, Info, Route } from "lucide-react"
import EmptyState from "../components/ui/EmptyState"
import ErrorState from "../components/ui/ErrorState"
import LoadingScreen from "../components/ui/LoadingScreen"
import PageHeader from "../components/ui/PageHeader"
import { useAvisos } from "../hooks/transit"
import type { TipoAviso } from "../types/transit"

const noticeIcons: Record<TipoAviso, typeof Info> = { atraso: AlertTriangle, desvio: Route, informacao: Info }

/** Lista os avisos, cada um com ícone e cor conforme o tipo. */
export default function NoticesPage() {
  const notices = useAvisos()

  if (notices.loading) return <LoadingScreen label="Carregando avisos..." />

  return (
    <div className="page page-soft">
      <PageHeader title="Avisos" subtitle="Mudanças na sua viagem" />
      <div className="page-body">
        {!notices.data ? (
          <ErrorState error={notices.error} onRetry={notices.reload} />
        ) : notices.data.length === 0 ? (
          <EmptyState icon={<Bell size={30} />} title="Tudo tranquilo" description="Não há avisos para as linhas no momento." />
        ) : (
          <div className="notice-list">
            {notices.data.map((notice) => {
              const Icon = noticeIcons[notice.tipo] ?? Info
              return (
                <article className={`notice-card ${notice.tipo}`} key={notice.id}>
                  <span className="notice-icon">
                    <Icon size={21} />
                  </span>
                  <div>
                    <span className="notice-time">{notice.horario}</span>
                    <h2>{notice.titulo}</h2>
                    <p>{notice.descricao}</p>
                    {notice.linhas.length > 0 && (
                      <div className="notice-lines">
                        Linhas {notice.linhas.map((line) => <b key={line}>{line}</b>)}
                      </div>
                    )}
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
