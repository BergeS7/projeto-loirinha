/** Contrato do streaming Firebase: SDKs simulados, sem chaves ou rede externa. */
import { afterEach, beforeEach, expect, it, vi } from "vitest"

const fake = vi.hoisted(() => ({
  callbacks: new Map<string, (snapshot: unknown) => void>(),
  auth: { currentUser: null as object | null, authStateReady: async () => {} },
  stops: [] as ReturnType<typeof vi.fn>[],
}))
vi.mock("../../config/firebase", () => ({
  getFirebase: () => ({ auth: fake.auth, db: {}, rtdb: {} }),
}))
vi.mock("firebase/auth", () => ({
  signInAnonymously: vi.fn(async () => {
    fake.auth.currentUser = {}
  }),
}))
vi.mock("firebase/firestore", () => ({
  collection: (_: unknown, path: string) => path,
  getDocsFromServer: vi.fn(async () => ({ docs: [] })),
  onSnapshot: (path: string, callback: (snapshot: unknown) => void) => {
    fake.callbacks.set(path, callback)
    const stop = vi.fn(() => fake.callbacks.delete(path))
    fake.stops.push(stop)
    return stop
  },
}))
vi.mock("firebase/database", () => ({
  ref: (_: unknown, path: string) => path,
  onValue: (path: string, callback: (snapshot: unknown) => void) => {
    fake.callbacks.set(path, callback)
    const stop = vi.fn(() => fake.callbacks.delete(path))
    fake.stops.push(stop)
    return stop
  },
}))

beforeEach(() => {
  vi.resetModules()
  vi.useFakeTimers()
  fake.callbacks.clear()
  fake.stops.length = 0
  fake.auth.currentUser = null
})
afterEach(() => vi.useRealTimers())

/** Entrega a assinatura assíncrona após autenticação/initialização do adaptador. */
async function flush() {
  for (let i = 0; i < 20; i++) await Promise.resolve()
}
function publish(path: string, value: unknown) {
  const callback = fake.callbacks.get(path)
  if (!callback) throw new Error(`Assinatura ausente: ${path}`)
  callback(path === "public_buses" ? { docs: [{ id: "b1", data: () => value }] } : { val: () => value })
}

it("expira GPS sem evento novo e remove todos os observadores ao sair", async () => {
  const { firebaseTransitService } = await import("./firebaseTransitService")
  const data = vi.fn()
  const stop = firebaseTransitService.subscribeOnibus!(undefined, data, vi.fn())
  await flush()
  publish("public_buses", { prefixo: "001", linhaId: "l1", sentido: "Fim" })
  publish(".info/connected", true)
  publish("telemetry", {
    b1: {
      linhaId: "l1",
      lat: -3.6,
      lng: -45.3,
      progresso: 0.5,
      updated_at: Date.now(),
      is_online: true,
      minutosProximoPonto: 2,
    },
  })
  expect(data.mock.lastCall?.[0][0].connectionStatus).toBe("online")
  vi.advanceTimersByTime(50_000)
  expect(data.mock.lastCall?.[0][0].connectionStatus).toBe("connection_lost")
  expect(data.mock.lastCall?.[0][0].minutosProximoPonto).toBeNull()
  stop()
  expect(fake.stops).toHaveLength(3)
  expect(fake.stops.every((unsubscribe) => unsubscribe.mock.calls.length === 1)).toBe(true)
  expect(vi.getTimerCount()).toBe(0)
})

it("cancelar durante a inicialização não deixa observadores ativos", async () => {
  const { firebaseTransitService } = await import("./firebaseTransitService")
  const data = vi.fn()
  const stop = firebaseTransitService.subscribeOnibus!(undefined, data, vi.fn())
  stop()
  await flush()
  expect(fake.callbacks.size).toBe(0)
  expect(data).not.toHaveBeenCalled()
})

it("consulta pontual sem resposta encerra com erro e libera timers/listeners", async () => {
  const { firebaseTransitService } = await import("./firebaseTransitService")
  const result = firebaseTransitService.getOnibus().catch((error) => error)
  await flush()
  await vi.advanceTimersByTimeAsync(10_001)
  expect(await result).toBeInstanceOf(Error)
  expect(fake.callbacks.size).toBe(0)
  expect(vi.getTimerCount()).toBe(0)
})

it("não exibe ônibus com linha divergente do catálogo", async () => {
  const { firebaseTransitService } = await import("./firebaseTransitService")
  const data = vi.fn()
  const stop = firebaseTransitService.subscribeOnibus!(undefined, data, vi.fn())
  await flush()
  publish("public_buses", { prefixo: "001", linhaId: "l1", sentido: "Fim" })
  publish(".info/connected", true)
  publish("telemetry", {
    b1: {
      linhaId: "outra",
      lat: -3.6,
      lng: -45.3,
      progresso: 0.5,
      updated_at: Date.now(),
      is_online: true,
    },
  })
  expect(data.mock.lastCall?.[0]).toEqual([])
  stop()
})
