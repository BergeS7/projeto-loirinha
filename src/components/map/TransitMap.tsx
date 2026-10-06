/**
 * Mapa base do app (Leaflet + OpenStreetMap), usado na tela inicial, no detalhe da linha e no
 * acompanhamento do ônibus.
 */
import { useEffect, useMemo } from "react"
import { CircleMarker, MapContainer, Polyline, TileLayer, useMap } from "react-leaflet"
import { CENTRO_SANTA_INES } from "../../config/constants"
import { getRoutePath } from "../../lib/route"
import type { Coordenada, LinhaResumo, Onibus, Ponto } from "../../types/transit"
import BusMarker from "./BusMarker"
import StopMarker from "./StopMarker"

function MapController({ center, follow, fitTo }: { center: Coordenada; follow?: Coordenada; fitTo?: Coordenada[] }) {
  const map = useMap()
  useEffect(() => {
    if (fitTo && fitTo.length > 1 && !follow) map.fitBounds(fitTo, { padding: [28, 28] })
    else map.flyTo(follow ?? center, follow ? 16 : map.getZoom(), { duration: 0.8 })
  }, [center, follow, fitTo, map])
  return null
}

type Props = {
  center?: Coordenada
  userPosition?: Coordenada
  points?: Ponto[]
  /** Ponto em destaque (ex.: próximo ponto do ônibus acompanhado). */
  highlightedPointId?: string
  buses?: Onibus[]
  /** Linhas dos ônibus exibidos, para mostrar número e cor de cada uma. */
  lines?: LinhaResumo[]
  /** Traçado (pelas ruas) de cada linha, por id: mantém os ônibus sobre a via. */
  tracados?: Record<string, Coordenada[]>
  /** Traçado desenhado no mapa. Deve seguir as ruas (venha de getTracado), nunca ligar pontos em linha reta. */
  route?: Coordenada[]
  routeColor?: string
  /** Enquadra o traçado inteiro ao carregar. */
  fitRoute?: boolean
  selectedBusId?: string
  interactive?: boolean
  className?: string
}

/**
 * Desenha o traçado da linha, os pontos fixos, os ônibus em movimento e a posição do usuário.
 * Também controla a câmera: centraliza, segue o ônibus selecionado ou enquadra o traçado inteiro.
 */
export default function TransitMap({
  center = CENTRO_SANTA_INES,
  userPosition,
  points = [],
  highlightedPointId,
  buses = [],
  lines = [],
  tracados,
  route,
  routeColor = "#f5b800",
  fitRoute = false,
  selectedBusId,
  interactive = true,
  className = "",
}: Props) {
  const followed = buses.find((bus) => bus.id === selectedBusId)
  const followPosition = useMemo<Coordenada | undefined>(
    () => (followed ? [followed.lat, followed.lng] : undefined),
    [followed?.lat, followed?.lng],
  )
  const lineById = useMemo(() => new Map(lines.map((line) => [line.id, line])), [lines])
  // Itinerários circulares repetem o ponto inicial no fim: um marcador por ponto basta.
  const uniquePoints = useMemo(() => [...new Map(points.map((point) => [point.id, point])).values()], [points])

  return (
    <MapContainer
      center={center}
      zoom={15}
      zoomControl={false}
      dragging={interactive}
      scrollWheelZoom={interactive}
      className={`transit-map ${className}`}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {route && route.length > 1 && (
        <>
          <Polyline positions={route} pathOptions={{ color: "#ffffff", weight: 8, opacity: 0.9 }} />
          <Polyline positions={route} pathOptions={{ color: routeColor, weight: 5, opacity: 1 }} />
        </>
      )}
      {uniquePoints.map((point) => (
        <StopMarker key={point.id} point={point} highlighted={point.id === highlightedPointId} />
      ))}
      {buses.map((bus) => (
        <BusMarker
          key={bus.id}
          bus={bus}
          line={lineById.get(bus.linhaId)}
          path={tracados?.[bus.linhaId]?.length ? getRoutePath(tracados[bus.linhaId]) : undefined}
          selected={bus.id === selectedBusId}
        />
      ))}
      {userPosition && (
        <>
          <CircleMarker center={userPosition} radius={13} pathOptions={{ fillColor: "#2d7ff9", fillOpacity: 0.16, stroke: false }} />
          <CircleMarker center={userPosition} radius={6} pathOptions={{ fillColor: "#2d7ff9", fillOpacity: 1, color: "white", weight: 2 }} />
        </>
      )}
      <MapController center={center} follow={followPosition} fitTo={fitRoute ? route : undefined} />
    </MapContainer>
  )
}
