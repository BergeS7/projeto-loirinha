import { Bell, BusFront, ChevronRight, LocateFixed, MapPin, Search, Star } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"
import { paths } from "../app/paths"
import TransitMap from "../components/map/TransitMap"
import BrandLogo from "../components/ui/BrandLogo"
import ErrorState from "../components/ui/ErrorState"
import { CENTRO_SANTA_INES } from "../config/constants"
import { useBusPositions, useLinhas, usePontos, usePontosProximos, useTracados } from "../hooks/transit"
import useFavorites from "../hooks/useFavorites"
import useGeolocation from "../hooks/useGeolocation"
import { saudacao } from "../lib/format"
import { minutosCaminhando } from "../lib/geo"
import type { Coordenada } from "../types/transit"

export default function HomePage() {
  const geo = useGeolocation()
  const origem = geo.status === "pending" ? undefined : (geo.position ?? CENTRO_SANTA_INES)
  // Nova referência a cada clique em "centralizar", para o mapa voar até lá mesmo sem mudar de posição.
  const [mapCenter, setMapCenter] = useState<Coordenada>()
  const [panelOpen, setPanelOpen] = useState(false)
  const [locationAlert, setLocationAlert] = useState(false)

  const nearby = usePontosProximos(origem)
  const linhas = useLinhas()
  const allStops = usePontos()
  const tracados = useTracados(linhas.data?.map((linha) => linha.id) ?? [])
  const buses = useBusPositions()
  const { favorites } = useFavorites()

  const favoriteLines = (linhas.data ?? []).filter((line) => favorites.linhas.includes(line.id)).slice(0, 3)
  const nearbyPoints = nearby.data ?? []

  const recenter = () => {
    if (geo.position) setMapCenter([...geo.position])
    else setLocationAlert(true)
  }

  return (
    <div className="home-page">
      <TransitMap
        center={mapCenter ?? origem}
        userPosition={geo.position}
        points={allStops.data ?? nearbyPoints}
        buses={buses}
        lines={linhas.data}
        tracados={tracados.data}
      />

      <header className="map-topbar">
        <div className="mini-brand">
          <BrandLogo size={34} />
          <div>
            <strong>Loirinha</strong>
            <small>Ônibus em tempo real</small>
          </div>
        </div>
        <Link to={paths.avisos} className="icon-button light" aria-label="Ver avisos">
          <Bell size={21} />
          <span className="notification-dot" />
        </Link>
      </header>

      <button type="button" className="locate-button" onClick={recenter} aria-label="Centralizar na minha localização">
        <LocateFixed size={22} />
      </button>

      <section className={`bottom-sheet ${panelOpen ? "open" : ""}`}>
        <button
          type="button"
          className="sheet-handle"
          onClick={() => setPanelOpen((value) => !value)}
          aria-label={panelOpen ? "Recolher painel" : "Expandir painel"}
          aria-expanded={panelOpen}
        >
          <span />
        </button>
        <div className="sheet-content">
          <p className="eyebrow">{saudacao()}</p>
          <h1>Onde vamos hoje?</h1>
          <Link to={paths.buscar} className="search-launcher">
            <Search size={21} />
            <span>Para onde você vai?</span>
            <ChevronRight size={20} />
          </Link>

          {(geo.status === "unavailable" || locationAlert) && (
            <div className="inline-alert">
              <MapPin size={18} />
              <span>Localização indisponível. Mostrando pontos no centro de Santa Inês.</span>
            </div>
          )}

          {favoriteLines.length > 0 && (
            <div className="quick-favorites">
              <div className="section-heading">
                <h2>Seus favoritos</h2>
                <Link to={paths.favoritos}>Ver todos</Link>
              </div>
              <div className="favorite-chips">
                {favoriteLines.map((line) => (
                  <Link to={paths.linha(line.id)} key={line.id}>
                    <Star size={15} fill="currentColor" /> Linha {line.numero}
                  </Link>
                ))}
              </div>
            </div>
          )}

          <div className="section-heading">
            <h2>Pontos perto de você</h2>
            {nearby.data && <span>{nearbyPoints.length} encontrados</span>}
          </div>
          <div className="nearby-list">
            {nearby.error && !nearby.data ? (
              <ErrorState error={nearby.error} onRetry={nearby.reload} />
            ) : !nearby.data ? (
              <div className="list-skeleton">{[1, 2, 3].map((item) => <span key={item} />)}</div>
            ) : (
              nearbyPoints.slice(0, panelOpen ? nearbyPoints.length : 3).map((point) => (
                <Link to={paths.ponto(point.id)} className="nearby-row" key={point.id}>
                  <span className="stop-symbol">
                    <BusFront size={19} />
                  </span>
                  <span className="row-main">
                    <strong>{point.nome}</strong>
                    <small>{point.referencia}</small>
                    <span className="line-dots">
                      {point.linhas.slice(0, 4).map((line) => (
                        <i key={line.id} style={{ backgroundColor: line.cor }}>
                          {line.numero}
                        </i>
                      ))}
                    </span>
                  </span>
                  <span className="distance" title="Tempo de caminhada">
                    {minutosCaminhando(point.distanciaKm)} min
                  </span>
                  <ChevronRight size={19} />
                </Link>
              ))
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
