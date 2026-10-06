/** Tela do ponto (/ponto/:id): próximos ônibus previstos, atualizados automaticamente. */
import { BusFront, Navigation, Users } from "lucide-react"
import { Link, useParams } from "react-router"
import { paths } from "../app/paths"
import EmptyState from "../components/ui/EmptyState"
import ErrorState from "../components/ui/ErrorState"
import FavoriteButton from "../components/ui/FavoriteButton"
import LoadingScreen from "../components/ui/LoadingScreen"
import PageHeader from "../components/ui/PageHeader"
import RouteBadge from "../components/ui/RouteBadge"
import { usePonto, usePrevisoes } from "../hooks/transit"
import useFavorites from "../hooks/useFavorites"
import { LOTACAO_LABEL } from "../lib/format"

/** Mostra o ponto da URL e as chegadas previstas, do ônibus mais próximo ao mais distante. */
export default function StopDetailPage() {
  const { id = "" } = useParams()
  const stop = usePonto(id)
  const arrivals = usePrevisoes(id)
  const { isFavorite, toggle } = useFavorites()

  if (stop.loading) return <LoadingScreen label="Buscando chegadas..." />
  if (stop.error !== undefined && !stop.data) {
    return (
      <div className="page">
        <PageHeader title="Ponto" />
        <ErrorState error={stop.error} onRetry={stop.reload} />
      </div>
    )
  }
  if (!stop.data) {
    return (
      <div className="page">
        <PageHeader title="Ponto não encontrado" />
        <EmptyState description="Confira o endereço e tente novamente." />
      </div>
    )
  }

  const point = stop.data
  const list = arrivals.data ?? []

  return (
    <div className="page page-soft">
      <PageHeader
        title={point.nome}
        subtitle={point.referencia}
        action={<FavoriteButton active={isFavorite("pontos", point.id)} onClick={() => toggle("pontos", point.id)} />}
      />
      <div className="page-body">
        <div className="update-pill">
          <span /> Atualizando ao vivo
        </div>
        <div className="section-heading roomy">
          <h2>Próximos ônibus</h2>
          <span>agora</span>
        </div>
        {arrivals.loading ? (
          <div className="search-loading" role="status">
            <span className="loader" /> Buscando chegadas...
          </div>
        ) : arrivals.error !== undefined && !arrivals.data ? (
          <ErrorState error={arrivals.error} onRetry={arrivals.reload} />
        ) : list.length === 0 ? (
          <EmptyState icon={<BusFront size={32} />} title="Nenhum ônibus previsto" description="Não há chegadas para este ponto no momento." />
        ) : (
          <div className="arrival-list">
            {list.map((arrival) => (
              <article className="arrival-card" key={arrival.onibusId}>
                <div className="arrival-route">
                  <RouteBadge linha={arrival.linha} />
                  <div>
                    <strong>{arrival.linha.nome}</strong>
                    <small>
                      <Users size={14} /> {LOTACAO_LABEL[arrival.lotacao]}
                    </small>
                  </div>
                </div>
                <div className="arrival-time">
                  <strong>{arrival.minutos}</strong>
                  <span>min</span>
                </div>
                <Link to={paths.acompanhar(arrival.linha.id, arrival.onibusId)} className="track-link">
                  <Navigation size={17} /> Acompanhar este ônibus
                </Link>
              </article>
            ))}
          </div>
        )}
        <p className="data-note">As previsões são estimativas e podem variar com o trânsito.</p>
      </div>
    </div>
  )
}
