/**
 * Tela de acompanhamento (/acompanhar/:linhaId/:onibusId): segue um ônibus no mapa e mostra a
 * previsão até o próximo ponto.
 */
import { BusFront, CheckCircle2, MapPin, Navigation, Users } from "lucide-react"
import { useParams } from "react-router"
import TransitMap from "../components/map/TransitMap"
import ErrorState from "../components/ui/ErrorState"
import LoadingScreen from "../components/ui/LoadingScreen"
import PageHeader from "../components/ui/PageHeader"
import { useBusPositions, useItinerario, useLinha, useTracado } from "../hooks/transit"
import { LOTACAO_LABEL } from "../lib/format"

/** Mapa seguindo o ônibus, tempo até o próximo ponto, barra de progresso e lotação. */
export default function TrackBusPage() {
  const { linhaId = "", onibusId = "" } = useParams()
  const line = useLinha(linhaId)
  const itinerary = useItinerario(linhaId)
  const tracado = useTracado(linhaId)
  const buses = useBusPositions(linhaId)

  if (line.loading) return <LoadingScreen label="Localizando ônibus..." />
  if (line.error !== undefined && !line.data) {
    return (
      <div className="page">
        <PageHeader title="Acompanhar ônibus" />
        <ErrorState error={line.error} onRetry={line.reload} />
      </div>
    )
  }
  if (!line.data) return <div className="page"><PageHeader title="Ônibus não encontrado" /></div>

  const linha = line.data
  const routePoints = itinerary.data ?? []
  const bus = buses.find((item) => item.id === onibusId)
  // O próximo ponto vem do backend (proximoPontoId); aqui só buscamos os dados dele no itinerário.
  const nextStop = routePoints.find((point) => point.id === bus?.proximoPontoId)
  // Barra limitada entre 12% e 90% para os ícones das pontas não ficarem por cima da linha.
  const progressPercent = Math.min(90, Math.max(12, (bus?.progresso ?? 0.2) * 100))

  return (
    <div className="track-page">
      <div className="track-header-overlay">
        <PageHeader title={`Linha ${linha.numero}`} subtitle={`Ônibus ${bus?.prefixo ?? "localizando..."}`} />
      </div>
      <TransitMap
        points={routePoints}
        highlightedPointId={nextStop?.id}
        buses={buses}
        lines={[linha]}
        tracados={tracado.data && { [linha.id]: tracado.data }}
        route={tracado.data}
        routeColor={linha.cor}
        selectedBusId={onibusId}
      />
      <section className="tracking-sheet">
        <div className="sheet-handle static">
          <span />
        </div>
        <div className="tracking-status" aria-live="polite">
          <div className="tracking-icon">
            <BusFront size={26} />
          </div>
          <div>
            <p>Seu ônibus está a caminho</p>
            <h1>
              {bus?.minutosProximoPonto != null ? (
                <>
                  Chega em cerca de <strong>{bus.minutosProximoPonto} min</strong>
                </>
              ) : (
                "Calculando chegada..."
              )}
            </h1>
          </div>
        </div>
        <div className="progress-route">
          <span className="progress-bus">
            <Navigation size={14} />
          </span>
          <div className="progress-line">
            <i style={{ width: `${progressPercent}%` }} />
          </div>
          <span className="progress-stop">
            <MapPin size={15} />
          </span>
        </div>
        <div className="tracking-meta">
          <div>
            <small>Próximo ponto</small>
            <strong>{nextStop?.nome ?? "Calculando..."}</strong>
          </div>
          <div>
            <small>Ocupação</small>
            <strong>
              <Users size={15} /> {bus ? LOTACAO_LABEL[bus.lotacao] : "—"}
            </strong>
          </div>
        </div>
        <div className="reassurance">
          <CheckCircle2 size={18} />
          <span>A posição atualiza automaticamente. Pode guardar o celular.</span>
        </div>
      </section>
    </div>
  )
}
