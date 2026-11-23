/** Encerramento continua disponível para motorista desativado sem esconder falhas de rede. */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import DriverPanel from "./DriverPanel"
import { BackendError } from "../../services/backend/errors"
const fake = vi.hoisted(() => ({ end: vi.fn(), out: vi.fn().mockResolvedValue({}) }))
vi.mock("../../config/firebase", () => ({ getFirebase: () => ({ db: {}, auth: { currentUser: { uid: "m1" } } }) }))
vi.mock("firebase/firestore", () => ({
  collection: vi.fn(),
  query: vi.fn(),
  where: vi.fn(),
  getDocs: async () => ({ docs: [{ id: "bus1" }] }),
}))
vi.mock("../../services/backend/functions", () => ({
  getMyRoute: async () => ({ route: { name: "Linha", stops: [] } }),
  checkIn: vi.fn(),
  checkOut: fake.out,
  endTelemetry: fake.end,
  sendTelemetry: vi.fn(),
}))
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})
it("libera ônibus mesmo que a desativação impeça endTelemetry", async () => {
  fake.end.mockRejectedValueOnce(new BackendError("permission-denied", "driver_inactive", "Inativo"))
  render(<DriverPanel />)
  await screen.findByText("Ônibus atual: bus1")
  fireEvent.click(screen.getByRole("button", { name: "Encerrar expediente" }))
  await waitFor(() => expect(fake.out).toHaveBeenCalledOnce())
})
it("não oculta falha de rede no encerramento", async () => {
  fake.end.mockRejectedValueOnce(new Error("offline"))
  render(<DriverPanel />)
  await screen.findByText("Ônibus atual: bus1")
  fireEvent.click(screen.getByRole("button", { name: "Encerrar expediente" }))
  await screen.findByRole("alert")
  expect(fake.out).not.toHaveBeenCalled()
})
