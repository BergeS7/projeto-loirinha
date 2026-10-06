import { VELOCIDADE_CAMINHADA_KMH } from "../config/constants"

type LatLng = { lat: number; lng: number }

/** Distância aproximada em km (projeção plana, suficiente para distâncias urbanas). */
export function distanciaKm(a: LatLng, b: LatLng) {
  const lat = (a.lat - b.lat) * 111
  const lng = (a.lng - b.lng) * 111 * Math.cos((a.lat * Math.PI) / 180)
  return Math.sqrt(lat * lat + lng * lng)
}

export function minutosCaminhando(km: number) {
  return Math.max(1, Math.round((km / VELOCIDADE_CAMINHADA_KMH) * 60))
}

/** Direção de `a` para `b` em graus: 0 = norte, 90 = leste (sentido horário). */
export function rumoGraus(a: LatLng, b: LatLng) {
  const dLat = b.lat - a.lat
  const dLng = (b.lng - a.lng) * Math.cos((a.lat * Math.PI) / 180)
  return ((Math.atan2(dLng, dLat) * 180) / Math.PI + 360) % 360
}
