/** Regressões de UX: ônibus ausente, erro e perda de sinal não prometem chegada. */
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import TrackBusPage from "./TrackBusPage"

const state = vi.hoisted(() => ({
  buses: {
    data: [] as Record<string, unknown>[],
    loading: false,
    error: undefined as unknown,
    reload: vi.fn(),
    updatedAt: Date.now(),
  },
}))
vi.mock("../components/map/TransitMap", () => ({
  default: () => <div>Mapa</div>,
}))
vi.mock("../hooks/useOnlineStatus", () => ({ default: () => true }))
vi.mock("../hooks/transit", () => ({
  useLinha: () => ({
    data: { id: "l1", numero: "101", nome: "Linha" },
    loading: false,
  }),
  useItinerario: () => ({ data: [], loading: false }),
  useTracado: () => ({ data: [], loading: false }),
  useBusPositions: () => state.buses,
}))
beforeEach(() => {
  state.buses.data = []
  state.buses.error = undefined
})
afterEach(cleanup)
function open() {
  return render(
    <MemoryRouter initialEntries={["/acompanhar/l1/b1"]}>
      <Routes>
        <Route path="/acompanhar/:linhaId/:onibusId" element={<TrackBusPage />} />
      </Routes>
    </MemoryRouter>,
  )
}
it("explica quando o ônibus não existe ou saiu de serviço", () => {
  open()
  expect(screen.getByText("Ônibus indisponível")).toBeDefined()
  expect(screen.queryByText("Calculando chegada...")).toBeNull()
})
it("oferece retry quando carregar a posição falha", () => {
  state.buses.error = new Error("falha")
  open()
  expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeDefined()
})
it("remove a previsão numérica quando o veículo perde o sinal", () => {
  state.buses.data = [
    {
      id: "b1",
      prefixo: "001",
      linhaId: "l1",
      progresso: 0.5,
      minutosProximoPonto: 2,
      connectionStatus: "connection_lost",
      lotacao: "desconhecida",
    },
  ]
  open()
  expect(screen.getByText("Previsão indisponível")).toBeDefined()
  expect(screen.getByText("Exibindo a última posição conhecida.")).toBeDefined()
})
