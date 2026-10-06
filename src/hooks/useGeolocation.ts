import { useEffect, useState } from "react"
import type { Coordenada } from "../types/transit"

export type GeolocationState =
  | { status: "pending"; position?: undefined }
  | { status: "granted"; position: Coordenada }
  | { status: "unavailable"; position?: undefined }

/** Pede a posição do usuário uma vez. Fica "unavailable" se negado, sem suporte ou sem HTTPS. */
export default function useGeolocation(): GeolocationState {
  const [state, setState] = useState<GeolocationState>(() =>
    "geolocation" in navigator ? { status: "pending" } : { status: "unavailable" },
  )

  useEffect(() => {
    if (!("geolocation" in navigator)) return
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => setState({ status: "granted", position: [coords.latitude, coords.longitude] }),
      () => setState({ status: "unavailable" }),
      { enableHighAccuracy: false, timeout: 6000, maximumAge: 60000 },
    )
  }, [])

  return state
}
