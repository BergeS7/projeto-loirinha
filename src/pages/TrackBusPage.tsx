/**
 * Tela de acompanhamento (/acompanhar/:linhaId/:onibusId): segue um ônibus no mapa e mostra a
 * previsão até o próximo ponto.
 */

import { BusFront, CheckCircle2, MapPin, Navigation, Users } from "lucide-react"

import { useParams } from "react-router"

import TransitMap from "../components/map/TransitMap"

import ErrorState from "../components/ui/ErrorState"

import EmptyState from "../components/ui/EmptyState"

import DataStatus from "../components/ui/DataStatus"

import LoadingScreen from "../components/ui/LoadingScreen"

import PageHeader from "../components/ui/PageHeader"

import { useBusPositions, useItinerario, useLinha, useTracado } from "../hooks/transit"

import { LOTACAO_LABEL } from "../lib/format"

import useOnlineStatus from "../hooks/useOnlineStatus"

/** Mapa seguindo o ônibus, tempo até o próximo ponto, barra de progresso e lotação. */

export default function TrackBusPage() {
  const { linhaId = "", onibusId = "" } = useParams()

  const line = useLinha(linhaId)

  const itinerary = useItinerario(linhaId)

  const tracado = useTracado(linhaId)

  const buses = useBusPositions(linhaId)

  const online = useOnlineStatus()

  if (line.loading) return <LoadingScreen label="Localizando ônibus..." />

  if (line.error !== undefined && !line.data) {
    return (
      <div className="page">
        <PageHeader title="Acompanhar ônibus" />
        <ErrorState error={line.error} onRetry={line.reload} />
      </div>
    )
  }

  if (!line.data)
    return (
      <div className="page">
        <PageHeader title="Ônibus não encontrado" />
      </div>
    )

  const linha = line.data

  const routePoints = itinerary.data ?? []

  const bus = buses.data?.find((item) => item.id === onibusId)

  if (buses.loading) return <LoadingScreen label="Localizando ônibus..." />

  if (!bus)
    return (
      <div className="page">
        <PageHeader title="Acompanhar ônibus" />
        {buses.error ? (
          <ErrorState error={buses.error} onRetry={buses.reload} />
        ) : (
          <EmptyState
            title="Ônibus indisponível"
            description="Este ônibus não foi encontrado ou está fora de serviço."
          />
        )}
      </div>
    )

  const lost = !online || bus.connectionStatus === "connection_lost" || buses.error !== undefined

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
        buses={buses.data ?? []}
        lines={[linha]}
        tracados={tracado.data && { [linha.id]: tracado.data }}
        route={tracado.data}
        routeColor={linha.cor}
        selectedBusId={onibusId}
      />
      <section className="tracking-sheet">
        <DataStatus {...buses} onRetry={buses.reload} />
        {itinerary.error !== undefined && (
          <ErrorState error={itinerary.error} onRetry={itinerary.reload} title="Itinerário indisponível" />
        )}
        {tracado.error !== undefined && (
          <ErrorState error={tracado.error} onRetry={tracado.reload} title="Traçado indisponível" />
        )}
        <div className="sheet-handle static">
          <span />
        </div>
        <div className="tracking-status" aria-live="polite">
          <div className="tracking-icon">
            <BusFront size={26} />
          </div>
          <div>
            <p>{lost ? "Ônibus sem atualização de posição" : "Ônibus em serviço"}</p>
            <h1>
              {!lost && bus.minutosProximoPonto != null ? (
                <>
                  Chega em cerca de <strong>{bus.minutosProximoPonto} min</strong>
                </>
              ) : (
                "Previsão indisponível"
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
          <span>{lost ? "Exibindo a última posição conhecida." : "Previsão até o próximo ponto do percurso."}</span>
        </div>
      </section>
    </div>
  )
}
