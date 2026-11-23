/** Adaptador do catálogo público Firebase. Nunca lê users, drivers ou buses privados. */
import { signInAnonymously } from "firebase/auth"
import { collection, getDocsFromServer, onSnapshot } from "firebase/firestore"
import { onValue, ref } from "firebase/database"
import { getFirebase } from "../../config/firebase"
import { env } from "../../config/env"
import { NetworkError } from "../../lib/http"
import { distanciaKm } from "../../lib/geo"
import { normalizarTexto } from "../../lib/format"
import type { Aviso, Coordenada, Linha, Onibus, Ponto } from "../../types/transit"
import type { TransitService } from "./TransitService"

/** Uma única autenticação atende consultas paralelas e preserva sessões existentes. */
let authentication: Promise<void> | undefined
async function ready() {
  const { auth } = getFirebase()
  authentication ??= (async () => {
    await auth.authStateReady()
    if (!auth.currentUser) await signInAnonymously(auth)
  })().finally(() => {
    authentication = undefined
  })
  await authentication
}

/** Limita espera e libera listeners; o SDK pode concluir internamente após cancelamento. */
function deadline<T>(operation: Promise<T>, signal?: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      window.clearTimeout(timer)
      signal?.removeEventListener("abort", abort)
    }
    const abort = () => {
      cleanup()
      reject(signal?.reason)
    }
    const timer = window.setTimeout(() => {
      cleanup()
      reject(new NetworkError("O Firebase demorou para responder."))
    }, env.requestTimeoutMs)
    if (signal?.aborted) {
      // A operação SDK já pode ter começado; consome sua rejeição após o cancelamento.
      void operation.catch(() => {})
      abort()
      return
    }
    signal?.addEventListener("abort", abort, { once: true })
    operation.then(
      (value) => {
        cleanup()
        resolve(value)
      },
      (error) => {
        cleanup()
        reject(error)
      },
    )
  })
}

/** Leituras do catálogo vêm do servidor; o service worker não guarda posições Firebase. */
async function list<T>(name: string, signal?: AbortSignal): Promise<T[]> {
  signal?.throwIfAborted()
  await deadline(ready(), signal)
  const snapshot = await deadline(getDocsFromServer(collection(getFirebase().db, name)), signal)
  signal?.throwIfAborted()
  return snapshot.docs.map((document) => ({ ...document.data(), id: document.id }) as T)
}

type PublicLine = Linha & {
  tracado: Coordenada[]
  pontoFracoes: number[]
  circular: boolean
}
/** Formato persistido evita arrays de arrays, que o Firestore não aceita. */
type StoredLine = Omit<PublicLine, "tracado"> & {
  tracado: {
    lat: number
    lng: number
  }[]
}
type PublicBus = {
  id: string
  linhaId: string
  prefixo: string
  sentido: string
}

/** Join por busId limita a exibição aos ônibus explicitamente publicados pelo dono. */
async function subscribe(
  linhaId: string | undefined,
  onData: (buses: Onibus[]) => void,
  onError: (error: unknown) => void,
  isActive: () => boolean,
) {
  await deadline(ready())
  if (!isActive()) return () => {}
  let buses: PublicBus[] | undefined
  let latest: Record<
    string,
    Onibus & {
      updated_at: number
      is_online: boolean
    }
  > = {}
  let received = false
  let failed = false
  let connected = false
  let wasConnected = false
  const fail = (error: unknown) => {
    failed = true
    if (isActive()) onError(error)
  }
  const emit = () => {
    if (!isActive() || !buses || !received || failed || !connected) return
    const now = Date.now()
    onData(
      buses
        .filter((bus) => !linhaId || bus.linhaId === linhaId)
        .flatMap((bus) => {
          const node = latest[bus.id]
          if (
            !node ||
            !Number.isFinite(node.lat) ||
            !Number.isFinite(node.lng) ||
            !Number.isFinite(node.progresso) ||
            node.linhaId !== bus.linhaId
          )
            return []
          const online = node.is_online && now - node.updated_at <= 45_000
          return [
            {
              ...node,
              ...bus,
              lotacao: node.lotacao ?? "desconhecida",
              updatedAt: node.updated_at,
              connectionStatus: online ? ("online" as const) : ("connection_lost" as const),
              minutosProximoPonto: online ? node.minutosProximoPonto : null,
            },
          ]
        }),
    )
  }
  // Catálogo também é observado: vincular ou retirar um ônibus aparece sem recarregar.
  const stopCatalog = onSnapshot(
    collection(getFirebase().db, "public_buses"),
    (snapshot) => {
      buses = snapshot.docs.map((document) => ({ ...document.data(), id: document.id }) as PublicBus)
      emit()
    },
    fail,
  )
  const stop = onValue(
    ref(getFirebase().rtdb, "telemetry"),
    (snapshot) => {
      latest = snapshot.val() ?? {}
      received = true
      emit()
    },
    fail,
  )
  const stopConnection = onValue(
    ref(getFirebase().rtdb, ".info/connected"),
    (snapshot) => {
      connected = snapshot.val() === true
      if (!connected && wasConnected) {
        if (isActive()) onError(new NetworkError())
        return
      }
      if (connected) {
        wasConnected = true
        emit()
      }
    },
    fail,
  )
  // Sem primeira resposta, a tela oferece retry em vez de carregar indefinidamente.
  const initialTimeout = window.setTimeout(() => {
    if (!received || !buses || !connected) fail(new NetworkError())
  }, env.requestTimeoutMs)
  // Expira também quando não chegam eventos (aparelho desligado/monitor atrasado).
  const timer = window.setInterval(emit, 5000)
  return () => {
    stop()
    stopCatalog()
    stopConnection()
    window.clearInterval(timer)
    window.clearTimeout(initialTimeout)
  }
}

/** Mesmo contrato das fontes mock/REST; somente a origem dos dados muda. */
export const firebaseTransitService: TransitService = {
  async getLinhas({ signal } = {}) {
    return (await list<StoredLine>("public_lines", signal)).map((line) => ({
      ...line,
      tracado: line.tracado.map(({ lat, lng }): Coordenada => [lat, lng]),
    }))
  },
  async getLinha(id, options) {
    return (await this.getLinhas(options)).find((line) => line.id === id) ?? null
  },
  async getPontos({ signal } = {}) {
    return list<Ponto>("public_stops", signal)
  },
  async getPonto(id, options) {
    return (await this.getPontos(options)).find((stop) => stop.id === id) ?? null
  },
  async getItinerario(id, options) {
    const [line, stops] = await Promise.all([this.getLinha(id, options), this.getPontos(options)])
    return (line?.pontoIds ?? []).flatMap((id) => stops.find((stop) => stop.id === id) ?? [])
  },
  async getTracado(id, options) {
    return ((await this.getLinha(id, options)) as PublicLine | null)?.tracado ?? []
  },
  async getPontosProximos([lat, lng], limite = 6, options) {
    const [stops, lines] = await Promise.all([this.getPontos(options), this.getLinhas(options)])
    return stops
      .map((stop) => ({
        ...stop,
        distanciaKm: distanciaKm({ lat, lng }, stop),
        linhas: lines
          .filter((line) => line.pontoIds.includes(stop.id))
          .map(({ id, numero, cor }) => ({ id, numero, cor })),
      }))
      .sort((a, b) => a.distanciaKm - b.distanciaKm)
      .slice(0, limite)
  },
  subscribeOnibus(linhaId, onData, onError) {
    let active = true
    let stop = () => {}
    void subscribe(linhaId, onData, onError, () => active)
      .then((unsubscribe) => {
        if (active) stop = unsubscribe
        else unsubscribe()
      })
      .catch((error) => {
        if (active) onError(error)
      })
    return () => {
      active = false
      stop()
    }
  },
  getOnibus(linhaId, { signal } = {}) {
    // Consulta pontual reutiliza a assinatura e sempre libera observador e cancelamento.
    return new Promise((resolve, reject) => {
      signal?.throwIfAborted()
      const cleanup = () => {
        stop()
        window.clearTimeout(timer)
        signal?.removeEventListener("abort", abort)
      }
      const abort = () => {
        cleanup()
        reject(signal?.reason)
      }
      const stop = this.subscribeOnibus!(
        linhaId,
        (data) => {
          cleanup()
          resolve(data)
        },
        (error) => {
          cleanup()
          reject(error)
        },
      )
      const timer = window.setTimeout(() => {
        cleanup()
        reject(new NetworkError())
      }, env.requestTimeoutMs)
      signal?.addEventListener("abort", abort, { once: true })
    })
  },
  async getPrevisoes(pontoId, options) {
    const [buses, lines] = await Promise.all([this.getOnibus(undefined, options), this.getLinhas(options)])
    // A projeção do servidor inclui ETA por parada, calculado pelo traçado e velocidade atual.
    return buses
      .flatMap((bus) => {
        const line = lines.find((line) => line.id === bus.linhaId)
        const minutes = (bus as Onibus & { previsoes?: Record<string, number> }).previsoes?.[pontoId]
        return line && bus.connectionStatus === "online" && minutes != null
          ? [
              {
                onibusId: bus.id,
                prefixo: bus.prefixo,
                linha: line,
                minutos: minutes,
                lotacao: bus.lotacao,
              },
            ]
          : []
      })
      .sort((a, b) => a.minutos - b.minutos)
  },
  getAvisos: ({ signal } = {}) => list<Aviso>("public_notices", signal),
  async buscar(termo, options) {
    const [lines, stops] = await Promise.all([this.getLinhas(options), this.getPontos(options)])
    const query = normalizarTexto(termo)
    return {
      linhas: lines.filter((line) => normalizarTexto(`${line.numero} ${line.nome}`).includes(query)),
      pontos: stops.filter((stop) => normalizarTexto(`${stop.nome} ${stop.referencia}`).includes(query)),
    }
  },
}
