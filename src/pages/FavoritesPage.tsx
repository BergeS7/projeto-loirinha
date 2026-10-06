import { BusFront, Heart, MapPin, Star } from "lucide-react"
import { Link } from "react-router"
import { paths } from "../app/paths"
import EmptyState from "../components/ui/EmptyState"
import ErrorState from "../components/ui/ErrorState"
import LoadingScreen from "../components/ui/LoadingScreen"
import PageHeader from "../components/ui/PageHeader"
import RouteBadge from "../components/ui/RouteBadge"
import { useLinhas, usePontos } from "../hooks/transit"
import useFavorites from "../hooks/useFavorites"

export default function FavoritesPage() {
  const { favorites, toggle } = useFavorites()
  const hasFavorites = favorites.linhas.length > 0 || favorites.pontos.length > 0
  const lines = useLinhas()
  const stops = usePontos()

  const favoriteLines = (lines.data ?? []).filter((line) => favorites.linhas.includes(line.id))
  const favoriteStops = (stops.data ?? []).filter((point) => favorites.pontos.includes(point.id))
  const error = lines.error ?? stops.error

  const content = () => {
    if (!hasFavorites) {
      return (
        <EmptyState
          variant="large"
          highlightIcon
          icon={<Heart size={34} />}
          title="Seus favoritos ficam aqui"
          description="Salve linhas e pontos para consultar os horários mais rápido."
        >
          <Link to={paths.buscar} className="primary-button">
            Buscar linha ou ponto
          </Link>
        </EmptyState>
      )
    }
    if (lines.loading || stops.loading) return <LoadingScreen label="Carregando favoritos..." />
    if (error !== undefined && !(lines.data && stops.data)) {
      return (
        <ErrorState
          error={error}
          onRetry={() => {
            lines.reload()
            stops.reload()
          }}
        />
      )
    }

    return (
      <>
        {favoriteLines.length > 0 && (
          <section>
            <div className="section-heading roomy">
              <h2>Linhas favoritas</h2>
              <span>{favoriteLines.length}</span>
            </div>
            <div className="card-list">
              {favoriteLines.map((line) => (
                <div className="favorite-row" key={line.id}>
                  <Link to={paths.linha(line.id)}>
                    <RouteBadge linha={line} />
                    <span>
                      <strong>{line.nome}</strong>
                      <small>{line.intervalo}</small>
                    </span>
                  </Link>
                  <button type="button" onClick={() => toggle("linhas", line.id)} aria-label="Remover linha dos favoritos">
                    <Star size={20} fill="currentColor" />
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}
        {favoriteStops.length > 0 && (
          <section>
            <div className="section-heading roomy">
              <h2>Pontos favoritos</h2>
              <span>{favoriteStops.length}</span>
            </div>
            <div className="card-list">
              {favoriteStops.map((point) => (
                <div className="favorite-row" key={point.id}>
                  <Link to={paths.ponto(point.id)}>
                    <span className="round-icon">
                      <BusFront size={19} />
                    </span>
                    <span>
                      <strong>{point.nome}</strong>
                      <small>
                        <MapPin size={13} /> {point.referencia}
                      </small>
                    </span>
                  </Link>
                  <button type="button" onClick={() => toggle("pontos", point.id)} aria-label="Remover ponto dos favoritos">
                    <Star size={20} fill="currentColor" />
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}
      </>
    )
  }

  return (
    <div className="page page-soft">
      <PageHeader title="Favoritos" subtitle="Seus atalhos do dia a dia" />
      <div className="page-body">{content()}</div>
    </div>
  )
}
