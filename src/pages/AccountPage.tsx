/** Acesso e perfil: não oferece seleção de papel nem permite autoelevação de privilégios. */
import { useState, type FormEvent } from "react"
import { Link, Navigate, useLocation, useNavigate } from "react-router"
import BrandLogo from "../components/ui/BrandLogo"
import useSession from "../hooks/useSession"
import { signIn, signOut } from "../services/backend/auth"
import { accountError, finishPassenger, registerPassenger, resetPassword } from "../services/backend/accounts"
import DriverPanel from "../components/account/DriverPanel"
import FleetPanel from "../components/account/FleetPanel"
import "../styles/account.css"

/** Campos de formulário são locais; senhas nunca vão para logs ou armazenamento local. */
export default function AccountPage() {
  const session = useSession()
  const navigate = useNavigate()
  const mode = useLocation().pathname.split("/").at(-1)
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmation, setConfirmation] = useState("")
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const member = session.user && !session.user.isAnonymous
  const registering = mode === "cadastro"
  const recovering = mode === "recuperar"
  const home =
    session.role === "motorista" ? "/conta/motorista" : session.role === "dono_frota" ? "/conta/frota" : "/conta/perfil"

  /** Mantém o usuário na tela se uma etapa do servidor falhar, permitindo retomar. */
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError("")
    setMessage("")
    setBusy(true)
    try {
      if (registering && password !== confirmation) throw new Error("confirmation")
      if (recovering) {
        try {
          await resetPassword(email)
        } catch (error) {
          if ((error as { code?: string }).code !== "auth/user-not-found") throw error
        }
        setMessage("Se houver uma conta com este e-mail, você receberá as instruções para definir sua senha.")
      } else if (registering) {
        await registerPassenger(name, email.trim(), password)
        navigate("/conta/perfil", { replace: true })
      } else {
        await signIn(email.trim(), password)
        navigate("/conta/perfil", { replace: true })
      }
    } catch (error) {
      setError(
        error instanceof Error && error.message === "confirmation"
          ? "As senhas precisam ser iguais."
          : accountError(error),
      )
    } finally {
      setBusy(false)
      setPassword("")
      setConfirmation("")
    }
  }

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
          Acesso temporariamente indisponível. Tente novamente mais tarde. Você pode continuar consultando o mapa.
        </p>
      )}
      {session.loading ? (
        <p role="status">Verificando sessão…</p>
      ) : member && !recovering ? (
        <>
          {(mode === "conta" || mode === "login" || mode === "cadastro" || mode === "perfil") &&
            session.role &&
            mode !== home.split("/").at(-1) && <Navigate to={home} replace />}
          <section className="account-card">
            <h1>Olá, {session.user?.displayName || "bem-vindo"}</h1>
            <p>{session.user?.email}</p>
            <p>
              Perfil:{" "}
              {session.role === "dono_frota"
                ? "Dono de frota"
                : session.role === "motorista"
                  ? "Motorista"
                  : session.role === "passageiro"
                    ? "Passageiro"
                    : "Cadastro pendente"}
            </p>
            {!session.role && (
              <>
                <p>Conclua o perfil de passageiro. Contas operacionais devem ser regularizadas pelo administrador.</p>
                <button
                  className="primary-button"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true)
                    try {
                      await finishPassenger(session.user?.displayName || "Passageiro")
                    } catch (e) {
                      setError(accountError(e))
                    } finally {
                      setBusy(false)
                    }
                  }}
                >
                  Concluir cadastro de passageiro
                </button>
              </>
            )}
            <button
              className="secondary-button"
              disabled={busy}
              onClick={async () => {
                setBusy(true)
                try {
                  await signOut()
                  navigate("/conta/login")
                } catch (e) {
                  setError(accountError(e))
                } finally {
                  setBusy(false)
                }
              }}
            >
              Sair da conta
            </button>
          </section>
          {session.role === "motorista" && <DriverPanel />}
          {session.role === "dono_frota" && <FleetPanel />}
          {session.role === "passageiro" && (
            <section className="account-card">
              <h2>Seus atalhos</h2>
              <Link to="/favoritos">Abrir favoritos</Link>
              <Link to="/">Ver ônibus no mapa</Link>
            </section>
          )}
          {((mode === "frota" && session.role !== "dono_frota") ||
            (mode === "motorista" && session.role !== "motorista")) && <Navigate to={home} replace />}
        </>
      ) : (
        <section className="account-card">
          <h1>{recovering ? "Recuperar senha" : registering ? "Criar conta de passageiro" : "Entre na sua conta"}</h1>
          <p>
            {registering
              ? "Motoristas são cadastrados pelo dono da frota."
              : "Acompanhe sua viagem ou acesse sua operação."}
          </p>
          <form onSubmit={submit}>
            {registering && (
              <label>
                Nome
                <input
                  required
                  maxLength={120}
                  autoComplete="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
            )}
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
                  minLength={registering ? 8 : 1}
                  maxLength={128}
                  autoComplete={registering ? "new-password" : "current-password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
            )}
            {registering && (
              <label>
                Confirmar senha
                <input
                  required
                  type="password"
                  minLength={8}
                  autoComplete="new-password"
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                />
              </label>
            )}
            <button className="primary-button" disabled={busy || session.error !== undefined}>
              {busy ? "Aguarde…" : recovering ? "Enviar instruções" : registering ? "Criar conta" : "Entrar"}
            </button>
          </form>
          <nav className="account-links">
            <Link to="/conta/login">Entrar</Link>
            <Link to="/conta/cadastro">Criar conta</Link>
            <Link to="/conta/recuperar">Esqueci minha senha</Link>
          </nav>
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
