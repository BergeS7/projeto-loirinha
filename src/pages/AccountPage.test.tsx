/** Fluxos de acesso sem rede, senha persistida ou criação de contas reais. */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, expect, it, vi } from "vitest"
import AccountPage from "./AccountPage"

const fake = vi.hoisted(() => ({
  login: vi.fn().mockResolvedValue({}),
  reset: vi.fn().mockResolvedValue(undefined),
}))
vi.mock("../hooks/useSession", () => ({ default: () => ({ loading: false, user: null, role: null }) }))
vi.mock("../services/backend/auth", () => ({ signIn: fake.login, signOut: vi.fn() }))
vi.mock("../services/backend/accounts", () => ({
  resetPassword: fake.reset,
  accountError: () => "Falha no serviço",
}))
vi.mock("../components/account/DriverPanel", () => ({ default: () => null }))
vi.mock("../components/account/FleetPanel", () => ({ default: () => null }))
vi.mock("../components/account/LiveBusesPanel", () => ({ default: () => null }))
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})
const open = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AccountPage />
    </MemoryRouter>,
  )
it("envia login com e-mail e senha", async () => {
  open("/conta/login")
  fireEvent.change(screen.getByLabelText("E-mail"), { target: { value: "p@example.test" } })
  fireEvent.change(screen.getByLabelText("Senha"), { target: { value: "senha-teste" } })
  fireEvent.submit(screen.getByRole("button", { name: "Entrar" }).closest("form")!)
  await waitFor(() => expect(fake.login).toHaveBeenCalledWith("p@example.test", "senha-teste"))
})
it("não oferece cadastro, porque o backend não tem function de cadastro", () => {
  open("/conta/login")
  expect(screen.queryByText("Criar conta")).toBeNull()
  expect(screen.getByText("Ainda não tem conta? As contas são criadas pela administração da frota.")).toBeTruthy()
})
it("recuperação mostra resposta neutra", async () => {
  open("/conta/recuperar")
  fireEvent.change(screen.getByLabelText("E-mail"), { target: { value: "p@example.test" } })
  fireEvent.submit(screen.getByRole("button", { name: "Enviar instruções" }).closest("form")!)
  expect(await screen.findByRole("status")).toHaveProperty(
    "textContent",
    "Se houver uma conta com este e-mail, você receberá as instruções para definir sua senha.",
  )
})
