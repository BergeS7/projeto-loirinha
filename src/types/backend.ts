/**
 * Tipos do backend Firebase, como estão gravados e devolvidos hoje (campos em snake_case, como no
 * backend). Fonte: docs/backend/BACKEND.md (seções 2 e 3).
 *
 * As telas não usam estes tipos diretamente: a conversão para os tipos do app (src/types/transit.ts)
 * deve ficar na camada de serviço. Veja docs/INTEGRACAO.md.
 */

/** Papel do usuário. Fonte oficial: custom claim `role` do ID token (nunca `users.role`). */
export type Role = "dono_frota" | "motorista" | "passageiro"

/** Lugar de uma rota (origem/destino). */
export type RoutePlace = { name: string; latitude: number; longitude: number }

/** Parada de uma rota. `order` é inteiro > 0, sem repetição. */
export type RouteStop = RoutePlace & { order: number }

/** Corpo de uma rota (entrada de `createRoute`). */
export type RouteBody = {
  name: string
  origin: RoutePlace
  destination: RoutePlace
  stops: RouteStop[]
  /** Cor da rota prevista (#RRGGBB). */
  color_hex_route: string
  /** Cor do desvio (#RRGGBB). */
  color_hex_out_route: string
}

/** Rota devolvida por `getBusRoute` e `getMyRoute` (sem `fleet_owner_id`). */
export type Route = RouteBody & { routeId: string }

/** Documento `buses/{busId}` (Firestore). Legível por qualquer usuário autenticado. */
export type BusDoc = {
  tag_code: string
  plate?: string
  model?: string
  capacity?: number
  fleet_owner_id: string
  /** UID do motorista com o ônibus; `null` = livre. */
  active_driver_id: string | null
}

export type TelemetryStatus = "in_service" | "delayed" | "out_of_route"
export type ConnectionStatus = "online" | "connection_lost"

/**
 * Nó `/telemetry/{busId}` (Realtime Database). Se o nó não existe, o ônibus está fora de serviço.
 * `speed` é a velocidade instantânea do GPS em km/h (inteiro). `updated_at` é a hora do servidor em
 * ms e é a única base para online/offline.
 */
export type TelemetryNode = {
  lat: number
  lng: number
  speed: number
  heading: number
  status: TelemetryStatus
  updated_at: number
  captured_at: number
  is_online: boolean
  connection_status: ConnectionStatus
  lat_anterior?: number
  long_anterior?: number
  /** Distância hipotética informada no envio (km). Não é a distância de um passageiro real. */
  distance?: number
}

export type ReleasedBus = { busId: string; tagCode: string | null }

export type CheckInResult = {
  success: true
  busId: string
  tagCode: string
  plate: string | null
  driverDocId: string
  driverId: string
  releasedBuses: ReleasedBus[]
  message: string
}

export type CheckOutResult = { success: true; driverId: string; releasedBuses: ReleasedBus[]; message: string }

export type CreateRouteResult = { success: true; routeId: string; message: string }

export type SetDriverRouteResult = { success: true; driverId: string; routeId: string; message: string }

export type BusRouteResult = { success: true; busId: string; driverDocId: string; route: Route }

export type MyRouteResult = { success: true; driverDocId: string; route: Route }

/** Entrada de `sendTelemetry`. Qualquer outro campo é recusado (`unexpected_field`). */
export type SendTelemetryInput = {
  busId: string
  lat: number
  lng: number
  /** km/h, de 0 a 200. */
  speed: number
  /** Graus, de 0 a 359. */
  heading: number
  status: TelemetryStatus
  /** Hora do fix no aparelho (Unix ms). */
  captured_at?: number
  /** Km, de 0 a 20000 (hipotética). */
  distance?: number
}

export type SendTelemetryResult = {
  success: true
  busId: string
  updated_at: number
  is_online: true
  connection_status: "online"
}

export type EndTelemetryResult = { success: true; busId: string; removed: boolean }
