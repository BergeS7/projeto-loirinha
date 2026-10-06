/**
 * Desenhos (HTML/SVG) dos marcadores do mapa. Ficam fora dos componentes para serem criados uma vez
 * e reaproveitados pelo Leaflet.
 */
import L from "leaflet"

/** Ícones dos marcadores. São HTML (divIcon) para poderem ser estilizados em styles/map.css. */

const escapeHtml = (text: string) => text.replace(/[&<>"']/g, (char) => `&#${char.charCodeAt(0)};`)

// Mesmo desenho do ícone BusFront do lucide-react, em SVG puro para caber no HTML do marcador.
const busSvg = (size: number) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6 2 7"/><path d="M10 6h4"/><path d="m22 7-2-1"/><rect width="16" height="16" x="4" y="3" rx="2"/><path d="M4 11h16"/><path d="M8 15h.01"/><path d="M16 15h.01"/><path d="M6 19v2"/><path d="M18 21v-2"/></svg>`

const BUS_SIZE = 44

// Ônibus visto de cima, com a frente para o norte. O marcador gira o desenho conforme a direção da via.
const busTopViewSvg = `<svg class="bus-vehicle" xmlns="http://www.w3.org/2000/svg" width="17" height="34" viewBox="0 0 24 48" aria-hidden="true">
  <rect x="0.5" y="7" width="3" height="4" rx="1" fill="#111"/><rect x="20.5" y="7" width="3" height="4" rx="1" fill="#111"/>
  <rect x="3" y="1" width="18" height="46" rx="4.5" fill="#F5B800" stroke="#111" stroke-opacity="0.55" stroke-width="1.2"/>
  <rect x="5" y="3.2" width="14" height="6.5" rx="2" fill="#1d2026"/>
  <rect x="5.5" y="12" width="13" height="29" rx="2" fill="#fff" fill-opacity="0.32"/>
  <rect x="8.5" y="17" width="7" height="5" rx="1" fill="#111" fill-opacity="0.18"/>
  <rect x="8.5" y="29" width="7" height="5" rx="1" fill="#111" fill-opacity="0.18"/>
  <rect x="6" y="42.5" width="12" height="2.8" rx="1" fill="#1d2026"/>
</svg>`

/** Veículo em movimento: ônibus visto de cima, girado na direção em que anda (estilo apps de mobilidade). */
export function busIcon({ selected }: { selected: boolean }) {
  return L.divIcon({
    className: "bus-marker-wrap",
    html: `<div class="bus-marker${selected ? " selected" : ""}">${busTopViewSvg}</div>`,
    iconSize: [BUS_SIZE, BUS_SIZE],
    // Centro do ônibus = posição do ônibus; a rotação acontece em torno dele.
    iconAnchor: [BUS_SIZE / 2, BUS_SIZE / 2],
    popupAnchor: [0, -BUS_SIZE / 2 + 4],
  })
}

const STOP_WIDTH = 30
const STOP_HEIGHT = 40

/** Ponto fixo: alfinete cuja ponta marca a localização exata da parada. */
export function stopIcon({ highlighted }: { highlighted: boolean }) {
  return L.divIcon({
    className: "stop-marker-wrap",
    html: `<div class="stop-marker${highlighted ? " highlighted" : ""}">
      <span class="stop-pin"><span class="stop-glyph">${busSvg(13)}</span></span>
      <span class="stop-ground"></span>
    </div>`,
    iconSize: [STOP_WIDTH, STOP_HEIGHT],
    // Ponta do alfinete (2px acima da base, sobre a sombra) = posição do ponto.
    iconAnchor: [STOP_WIDTH / 2, STOP_HEIGHT - 2],
    popupAnchor: [0, -STOP_HEIGHT + 4],
  })
}
