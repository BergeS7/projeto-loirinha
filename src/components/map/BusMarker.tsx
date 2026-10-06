/**
 * Marcador de ônibus no mapa: veículo visto de cima que anda pelo traçado da linha e gira conforme
 * a direção da rua.
 */
import type L from "leaflet"
import { useEffect, useMemo, useRef, useState } from "react"
import { Link } from "react-router"
import { Marker, Popup } from "react-leaflet"
import { paths } from "../../app/paths"
import { REFRESH_INTERVAL } from "../../config/constants"
import { LOTACAO_LABEL } from "../../lib/format"
import { rumoGraus } from "../../lib/geo"
import { type RoutePath, pointAlong } from "../../lib/route"
import type { LinhaResumo, Onibus } from "../../types/transit"
import { busIcon } from "./markerIcons"

/** Avanços maiores que isso (ex.: ônibus que voltou ao início da linha) não são animados. */
const MAX_ANIMATED_M = 600

const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches

type Props = {
  bus: Onibus
  line?: LinhaResumo
  /** Traçado da linha. Com ele, o ônibus anda pela rua; sem ele, só é reposicionado. */
  path?: RoutePath
  selected: boolean
}

/**
 * Ônibus no mapa. Com o traçado da linha, desliza pela rua entre uma atualização e outra
 * (nunca em linha reta por cima de quarteirões) e a seta acompanha a direção da via.
 */
export default function BusMarker({ bus, line, path, selected }: Props) {
  const markerRef = useRef<L.Marker>(null)
  const headingRef = useRef<number | null>(null)
  // Ângulo acumulado já aplicado: evita que o ônibus dê uma volta inteira ao passar de 359° para 1°.
  const renderedAngleRef = useRef<number | null>(null)
  const progressRef = useRef<number | null>(null)
  // Posição inicial fixa: depois disso, quem move o marcador são os efeitos abaixo.
  const [initialPosition] = useState<[number, number]>(() =>
    path ? pointAlong(path, bus.progresso).position : [bus.lat, bus.lng],
  )

  const label = line?.numero ?? bus.prefixo.split("-")[0]
  const icon = useMemo(() => busIcon({ selected }), [selected])

  const applyHeading = () => {
    const element = markerRef.current?.getElement()?.querySelector<SVGElement>(".bus-vehicle")
    if (!element || headingRef.current === null) return
    const previous = renderedAngleRef.current ?? headingRef.current
    const delta = ((headingRef.current - previous + 540) % 360) - 180
    renderedAngleRef.current = previous + delta
    element.style.transform = `rotate(${renderedAngleRef.current}deg)`
  }

  // Trocar o ícone recria o HTML do marcador: reaplica a direção.
  useEffect(applyHeading, [icon])

  useEffect(() => {
    const marker = markerRef.current
    if (!marker) return

    if (!path) {
      // Sem traçado não dá para saber por onde a rua passa: reposiciona sem interpolar.
      const from = marker.getLatLng()
      if (from.lat !== bus.lat || from.lng !== bus.lng) headingRef.current = rumoGraus(from, bus)
      marker.setLatLng([bus.lat, bus.lng])
      applyHeading()
      return
    }

    const placeAt = (progresso: number) => {
      const { position, heading } = pointAlong(path, progresso)
      marker.setLatLng(position)
      headingRef.current = heading
      progressRef.current = progresso
      applyHeading()
    }

    const from = progressRef.current ?? bus.progresso
    const to = bus.progresso
    const advance = (to - from) * path.total
    if (advance <= 0 || advance > MAX_ANIMATED_M || prefersReducedMotion()) {
      placeAt(to)
      return
    }

    // Avança pela rua durante o intervalo de atualização: o ônibus parece andar sem parar.
    const duration = REFRESH_INTERVAL.posicoesOnibus
    const start = performance.now()
    let frame = 0
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      placeAt(from + (to - from) * t)
      if (t < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [bus.progresso, bus.lat, bus.lng, path])

  return (
    <Marker
      ref={markerRef}
      position={initialPosition}
      icon={icon}
      zIndexOffset={selected ? 1000 : 500}
      title={`Ônibus ${bus.prefixo}, linha ${label}`}
      alt={`Ônibus ${bus.prefixo}`}
    >
      <Popup>
        <div className="map-popup">
          <strong>Ônibus {bus.prefixo}</strong>
          <small>
            Linha {label} · sentido {bus.sentido}
          </small>
          <small>{LOTACAO_LABEL[bus.lotacao]}</small>
          {!selected && <Link to={paths.acompanhar(bus.linhaId, bus.id)}>Acompanhar</Link>}
        </div>
      </Popup>
    </Marker>
  )
}
