/** Fluxos de acesso sem rede, senha persistida ou criação de contas reais. */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, expect, it, vi } from "vitest"
import AccountPage from "./AccountPage"

const fake = vi.hoisted(() => ({
  login: vi.fn().mockResolvedValue({}),
  register: vi.fn(),
  reset: vi.fn().mockResolvedValue(undefined),
}))
vi.mock("../hooks/useSession", () => ({ default: () => ({ loading: false, user: null, role: null }) }))
vi.mock("../services/backend/auth", () => ({ signIn: fake.login, signOut: vi.fn() }))
vi.mock("../services/backend/accounts", () => ({
  registerPassenger: fake.register,
  finishPassenger: vi.fn(),
  resetPassword: fake.reset,
  accountError: () => "Falha no serviço",
}))
vi.mock("../components/account/DriverPanel", () => ({ default: () => null }))
vi.mock("../components/account/FleetPanel", () => ({ default: () => null }))
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
it("não cadastra senhas divergentes", async () => {
  open("/conta/cadastro")
  fireEvent.change(screen.getByLabelText("Senha"), { target: { value: "senha-12345" } })
  fireEvent.change(screen.getByLabelText("Confirmar senha"), { target: { value: "outra-12345" } })
  fireEvent.submit(screen.getByRole("button", { name: "Criar conta" }).closest("form")!)
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "As senhas precisam ser iguais.")
  expect(fake.register).not.toHaveBeenCalled()
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
