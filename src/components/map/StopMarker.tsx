/** Marcador de ponto de ônibus no mapa: alfinete fixo com balão de informações. */
import { useMemo } from "react"
import { Link } from "react-router"
import { Marker, Popup } from "react-leaflet"
import { paths } from "../../app/paths"
import type { Ponto } from "../../types/transit"
import { stopIcon } from "./markerIcons"

type Props = {
  point: Ponto
  highlighted?: boolean
}

/** Ponto de ônibus: marcador fixo, com a ponta do alfinete na localização exata da parada. */
export default function StopMarker({ point, highlighted = false }: Props) {
  const icon = useMemo(() => stopIcon({ highlighted }), [highlighted])

  return (
    <Marker
      position={[point.lat, point.lng]}
      icon={icon}
      zIndexOffset={highlighted ? 300 : 0}
      title={`Ponto ${point.nome}`}
      alt={`Ponto ${point.nome}`}
    >
      <Popup>
        <div className="map-popup">
          <strong>{point.nome}</strong>
          <small>{point.referencia}</small>
          <Link to={paths.ponto(point.id)}>Ver próximos ônibus</Link>
        </div>
      </Popup>
    </Marker>
  )
}
