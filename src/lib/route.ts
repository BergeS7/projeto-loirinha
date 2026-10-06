/**
 * Geometria dos traçados das linhas: comprimento, posição pela distância percorrida e direção da
 * rua. É o que mantém os ônibus sobre as vias no mapa.
 */
import type { Coordenada } from "../types/transit"
import { rumoGraus } from "./geo"

/** Traçado de uma linha preparado para localizar posições pela distância percorrida. */
export type RoutePath = {
  coords: Coordenada[]
  /** Distância acumulada (m) até cada vértice. */
  cumulative: number[]
  /** Comprimento total (m). */
  total: number
}

const RAIO_TERRA_M = 6_371_000
const rad = (graus: number) => (graus * Math.PI) / 180

/** Distância em metros entre duas coordenadas (fórmula de Haversine). */
export function metrosEntre([lat1, lng1]: Coordenada, [lat2, lng2]: Coordenada) {
  const h = Math.sin(rad(lat2 - lat1) / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lng2 - lng1) / 2) ** 2
  return 2 * RAIO_TERRA_M * Math.asin(Math.sqrt(h))
}

/** Prepara um traçado calculando a distância acumulada até cada vértice. */
export function buildRoutePath(coords: Coordenada[]): RoutePath {
  const cumulative = [0]
  for (let i = 1; i < coords.length; i++) cumulative.push(cumulative[i - 1] + metrosEntre(coords[i - 1], coords[i]))
  return { coords, cumulative, total: cumulative.at(-1) ?? 0 }
}

// Traçados não mudam depois de carregados: cada array é preparado uma vez só.
const cache = new WeakMap<Coordenada[], RoutePath>()

/** Igual a buildRoutePath, mas com cache: cada array de coordenadas é preparado uma vez só. */
export function getRoutePath(coords: Coordenada[]): RoutePath {
  let path = cache.get(coords)
  if (!path) {
    path = buildRoutePath(coords)
    cache.set(coords, path)
  }
  return path
}

/**
 * Posição sobre o traçado após percorrer `fracao` do comprimento (0 = início, 1 = fim),
 * e a direção da rua naquele trecho. A posição fica sempre sobre a via.
 */
export function pointAlong(path: RoutePath, fracao: number): { position: Coordenada; heading: number } {
  const { coords, cumulative, total } = path
  if (coords.length < 2) return { position: coords[0] ?? [0, 0], heading: 0 }

  const alvo = Math.min(Math.max(fracao, 0), 1) * total
  // Busca binária pelo trecho que contém a distância alvo.
  let lo = 0
  let hi = cumulative.length - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (cumulative[mid] <= alvo) lo = mid
    else hi = mid
  }

  const [a, b] = [coords[lo], coords[hi]]
  const trecho = cumulative[hi] - cumulative[lo]
  const t = trecho > 0 ? (alvo - cumulative[lo]) / trecho : 0
  return {
    position: [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t],
    heading: rumoGraus({ lat: a[0], lng: a[1] }, { lat: b[0], lng: b[1] }),
  }
}
