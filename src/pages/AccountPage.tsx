/**
 * Acesso e área de cada papel, usando só o backend original (backend/):
 * - login com e-mail e senha e recuperação de senha (Firebase Authentication);
 * - motorista: check-in, rota e envio de GPS (DriverPanel);
 * - dono de frota: ônibus, motoristas e rotas da frota (FleetPanel);
 * - passageiro: ônibus em serviço, ao vivo (LiveBusesPanel).
 *
 * Não há cadastro pelo app: o backend não tem function de cadastro, e uma conta criada no cliente
 * nasceria sem papel. As contas são criadas pela administração (backend/scripts/seed_and_call.py).
 */
import { useState, type FormEvent } from "react"
import { Link, Navigate, useLocation, useNavigate } from "react-router"
import BrandLogo from "../components/ui/BrandLogo"
import useSession from "../hooks/useSession"
import { signIn, signOut } from "../services/backend/auth"
import { accountError, resetPassword } from "../services/backend/accounts"
import DriverPanel from "../components/account/DriverPanel"
import FleetPanel from "../components/account/FleetPanel"
import LiveBusesPanel from "../components/account/LiveBusesPanel"
import type { Role } from "../types/backend"
import "../styles/account.css"

const ROLE_LABEL: Record<Role, string> = {
  dono_frota: "Dono de frota",
  motorista: "Motorista",
  passageiro: "Passageiro",
}

/** Caminho da área de cada papel. */
const ROLE_PATH: Record<Role, string> = {
  dono_frota: "/conta/frota",
  motorista: "/conta/motorista",
  passageiro: "/conta/perfil",
}

/** Os campos são locais; a senha nunca vai para logs ou armazenamento local. */
export default function AccountPage() {
  const session = useSession()
  const navigate = useNavigate()
  const mode = useLocation().pathname.split("/").filter(Boolean).at(-1) ?? "conta"
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const recovering = mode === "recuperar"
  const logged = Boolean(session.user && !session.user.isAnonymous)
  const home = session.role ? ROLE_PATH[session.role] : "/conta/perfil"

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError("")
    setMessage("")
    setBusy(true)
    try {
      if (recovering) {
        try {
          await resetPassword(email)
        } catch (error) {
          if ((error as { code?: string }).code !== "auth/user-not-found") throw error
        }
        setMessage("Se houver uma conta com este e-mail, você receberá as instruções para definir sua senha.")
      } else {
        await signIn(email.trim(), password)
      }
    } catch (error) {
      setError(accountError(error))
    } finally {
      setBusy(false)
      setPassword("")
    }
  }

  const logout = async () => {
    setBusy(true)
    setError("")
    try {
      await signOut()
      navigate("/conta/login", { replace: true })
    } catch (e) {
      setError(accountError(e))
    } finally {
      setBusy(false)
    }
  }

  // Leva cada papel para a sua área; impede abrir a área de outro papel pela URL.
  const wrongArea =
    logged &&
    !recovering &&
    session.role !== null &&
    `/conta/${mode}` !== home &&
    ["conta", "login", "perfil", "motorista", "frota"].includes(mode)

  return (
    <div className="account-page">
      <header className="account-brand">
        <BrandLogo size={42} />
        <div>
          <strong>Loirinha</strong>
          <p>Sua viagem começa aqui</p>
        </div>
        <Link to="/">Voltar ao mapa</Link>
      </header>
      {session.error !== undefined && (
        <p className="account-error" role="status">
          Acesso temporariamente indisponível. Você pode continuar consultando o mapa.
        </p>
      )}
      {session.loading ? (
        <p role="status">Verificando sessão…</p>
      ) : logged && !recovering ? (
        <>
          {wrongArea && <Navigate to={home} replace />}
          <section className="account-card">
            <h1>Olá, {session.user?.displayName || session.user?.email?.split("@")[0] || "bem-vindo"}</h1>
            <p>{session.user?.email}</p>
            <p>Perfil: {session.role ? ROLE_LABEL[session.role] : "sem perfil definido"}</p>
            {!session.role && (
              <p>
                Sua conta ainda não tem um perfil (motorista, dono de frota ou passageiro). Peça à administração para
                definir o perfil e entre de novo.
              </p>
            )}
            <button className="secondary-button" disabled={busy} onClick={() => void logout()}>
              Sair da conta
            </button>
          </section>
          {session.role === "motorista" && <DriverPanel />}
          {session.role === "dono_frota" && <FleetPanel />}
          {session.role === "passageiro" && <LiveBusesPanel />}
        </>
      ) : (
        <section className="account-card">
          <h1>{recovering ? "Recuperar senha" : "Entre na sua conta"}</h1>
          <p>
            {recovering
              ? "Informe o e-mail da sua conta."
              : "Motoristas, donos de frota e passageiros cadastrados entram aqui."}
          </p>
          <form onSubmit={submit}>
            <label>
              E-mail
              <input
                required
                type="email"
                maxLength={254}
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            {!recovering && (
              <label>
                Senha
                <input
                  required
                  type="password"
                  maxLength={128}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
            )}
            <button className="primary-button" disabled={busy || session.error !== undefined}>
              {busy ? "Aguarde…" : recovering ? "Enviar instruções" : "Entrar"}
            </button>
          </form>
          <nav className="account-links">
            {recovering ? <Link to="/conta/login">Voltar para entrar</Link> : <Link to="/conta/recuperar">Esqueci minha senha</Link>}
          </nav>
          <p>Ainda não tem conta? As contas são criadas pela administração da frota.</p>
        </section>
      )}
      {error && (
        <p className="account-error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="account-success" role="status">
          {message}
        </p>
      )}
    </div>
  )
}
