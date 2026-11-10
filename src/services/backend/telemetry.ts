/**
 * Leitura em tempo real de /telemetry no Realtime Database. Exige usuário autenticado (regra
 * `auth != null`); o cliente nunca grava (quem grava é `sendTelemetry`).
 */
import { onValue, ref } from "firebase/database"
import { getFirebase } from "../../config/firebase"
import type { TelemetryNode } from "../../types/backend"

/** Ônibus em serviço, por busId. Ônibus ausente = fora de serviço. */
export type TelemetrySnapshot = Record<string, TelemetryNode>

/** Escuta todos os ônibus em serviço. Devolve a função para cancelar. */
export function subscribeTelemetry(callback: (data: TelemetrySnapshot) => void, onError?: (error: Error) => void) {
  return onValue(
    ref(getFirebase().rtdb, "telemetry"),
    (snapshot) => callback((snapshot.val() as TelemetrySnapshot | null) ?? {}),
    onError,
  )
}

/** Escuta um ônibus. `null` = fora de serviço (nó ausente). */
export function subscribeBusTelemetry(
  busId: string,
  callback: (node: TelemetryNode | null) => void,
  onError?: (error: Error) => void,
) {
  return onValue(
    ref(getFirebase().rtdb, `telemetry/${busId}`),
    (snapshot) => callback((snapshot.val() as TelemetryNode | null) ?? null),
    onError,
  )
}
