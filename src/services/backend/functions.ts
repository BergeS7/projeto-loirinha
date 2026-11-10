/**
 * Uma função por callable do backend (backend/functions/main.py). O SDK anexa o ID token do usuário
 * logado; o backend tira uid e papel só do token, nunca do payload.
 * Entradas e saídas: docs/backend/BACKEND.md, seção 3.
 */
import { httpsCallable } from "firebase/functions"
import { getFirebase } from "../../config/firebase"
import type {
  BusRouteResult,
  CheckInResult,
  CheckOutResult,
  CreateRouteResult,
  EndTelemetryResult,
  MyRouteResult,
  RouteBody,
  SendTelemetryInput,
  SendTelemetryResult,
  SetDriverRouteResult,
} from "../../types/backend"
import { toBackendError } from "./errors"

/** Chama a callable `name` e devolve `result.data`. Erros viram BackendError (com `reason`). */
async function call<Req, Res>(name: string, data?: Req): Promise<Res> {
  try {
    const fn = httpsCallable<Req | undefined, Res>(getFirebase().functions, name)
    const result = await fn(data)
    return result.data
  } catch (error) {
    throw toBackendError(error)
  }
}

/** Motorista assume o ônibus da tag. */
export const checkIn = (tagCode: string) => call<{ tagCode: string }, CheckInResult>("checkIn", { tagCode })

/** Motorista libera os próprios ônibus (fim de expediente). Chame `endTelemetry` antes. */
export const checkOut = () => call<undefined, CheckOutResult>("checkOut")

/** Dono da frota cadastra uma rota na própria frota. */
export const createRoute = (route: RouteBody) => call<RouteBody, CreateRouteResult>("createRoute", route)

/** Dono da frota atribui uma rota da frota a um motorista da frota (IDs de documento). */
export const setDriverRoute = (driverId: string, routeId: string) =>
  call<{ driverId: string; routeId: string }, SetDriverRouteResult>("setDriverRoute", { driverId, routeId })

/** Dono da frota consulta a rota do motorista ativo de um ônibus seu. */
export const getBusRoute = (busId: string) => call<{ busId: string }, BusRouteResult>("getBusRoute", { busId })

/** Motorista lê a própria rota. Não envia payload (campos extras dão `unexpected_field`). */
export const getMyRoute = () => call<undefined, MyRouteResult>("getMyRoute")

/** Heartbeat do celular do ônibus (a cada ~15-20 s). */
export const sendTelemetry = (input: SendTelemetryInput) =>
  call<SendTelemetryInput, SendTelemetryResult>("sendTelemetry", input)

/** Fim normal da viagem: remove /telemetry/{busId}. */
export const endTelemetry = (busId: string) => call<{ busId: string }, EndTelemetryResult>("endTelemetry", { busId })
