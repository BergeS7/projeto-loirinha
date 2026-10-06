import { BusFront, ChevronRight, Clock3, MapPin } from "lucide-react"
import { useState } from "react"
import { Link, useParams } from "react-router"
import { paths } from "../app/paths"
import TransitMap from "../components/map/TransitMap"
import EmptyState from "../components/ui/EmptyState"
import ErrorState from "../components/ui/ErrorState"
import FavoriteButton from "../components/ui/FavoriteButton"
import LoadingScreen from "../components/ui/LoadingScreen"
import PageHeader from "../components/ui/PageHeader"
import { useBusPositions, useItinerario, useLinha, useTracado } from "../hooks/transit"
import useFavorites from "../hooks/useFavorites"

const PONTOS_VISIVEIS = 6

export default function LineDetailPage() {
  const { id = "" } = useParams()
  const line = useLinha(id)
  const itinerary = useItinerario(id)
  const tracado = useTracado(id)
  const buses = useBusPositions(id)
  const [showAll, setShowAll] = useState(false)
  const { isFavorite, toggle } = useFavorites()

  if (line.loading || itinerary.loading) return <LoadingScreen label="Carregando linha..." />
  const error = line.error ?? itinerary.error
  if (error !== undefined && !line.data) {
    return (
      <div className="page">
        <PageHeader title="Linha" />
        <ErrorState
          error={error}
          onRetry={() => {
            line.reload()
            itinerary.reload()
          }}
        />
      </div>
    )
  }
  if (!line.data) {
    return (
      <div className="page">
        <PageHeader title="Linha não encontrada" />
        <EmptyState description="Confira o endereço e tente novamente." />
      </div>
    )
  }

  const linha = line.data
  const routePoints = itinerary.data ?? []

  return (
    <div className="page line-page">
      <PageHeader
        title={`Linha ${linha.numero}`}
        subtitle={linha.nome}
        action={<FavoriteButton active={isFavorite("linhas", linha.id)} onClick={() => toggle("linhas", linha.id)} />}
      />
      <div className="line-map-wrap">
        <TransitMap
          center={routePoints[0] ? [routePoints[0].lat, routePoints[0].lng] : undefined}
          points={routePoints}
          buses={buses}
          lines={[linha]}
          tracados={tracado.data && { [linha.id]: tracado.data }}
          route={tracado.data}
          fitRoute
          routeColor={linha.cor}
          className="line-map"
        />
        <div className="live-buses">
          <span /> {buses.length} ônibus circulando
        </div>
      </div>
      <div className="page-body line-details">
        <div className="operation-card">
          <Clock3 size={20} />
          <div>
            <small>Horário de operação</small>
            <strong>{linha.operacao}</strong>
          </div>
          <div>
            <small>Frequência</small>
            <strong>{linha.intervalo}</strong>
          </div>
        </div>
        <div className="section-heading roomy">
          <h2>Itinerário</h2>
          <span>{routePoints.length} pontos</span>
        </div>
        <div className="route-stop-list">
          {routePoints.slice(0, showAll ? routePoints.length : PONTOS_VISIVEIS).map((point, index) => (
            <Link to={paths.ponto(point.id)} key={`${point.id}-${index}`} className="route-stop">
              <span className="route-track">
                <i style={{ borderColor: linha.cor }} />
              </span>
              <span>
                <strong>{point.nome}</strong>
                <small>{point.referencia}</small>
              </span>
              <ChevronRight size={18} />
            </Link>
          ))}
        </div>
        {routePoints.length > PONTOS_VISIVEIS && (
          <button type="button" className="secondary-button" onClick={() => setShowAll((value) => !value)}>
            <MapPin size={18} /> {showAll ? "Mostrar menos" : `Ver todos os ${routePoints.length} pontos`}
          </button>
        )}
        <div className="section-heading roomy">
          <h2>Ônibus desta linha</h2>
        </div>
        <div className="bus-list">
          {buses.map((bus) => (
            <Link to={paths.acompanhar(linha.id, bus.id)} className="bus-row" key={bus.id}>
              <span className="round-icon yellow">
                <BusFront size={19} />
              </span>
              <span>
                <strong>Ônibus {bus.prefixo}</strong>
                <small>Sentido {bus.sentido}</small>
              </span>
              <span className="online-label">Em movimento</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
