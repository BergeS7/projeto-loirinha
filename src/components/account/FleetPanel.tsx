/** Administração restrita à frota: o servidor revalida cada leitura e alteração. */
import { useCallback, useEffect, useState, type FormEvent } from "react"
import { accountCall, accountError, resetPassword, type FleetUser } from "../../services/backend/accounts"
import { setDriverRoute } from "../../services/backend/functions"

export default function FleetPanel() {
  const [users, setUsers] = useState<FleetUser[]>([])
  const [routes, setRoutes] = useState<{ id: string; name: string }[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [routeIds, setRouteIds] = useState<Record<string, string>>({})
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const reload = useCallback(async () => {
    const [result, available] = await Promise.all([
      accountCall<{ users: FleetUser[]; hasMore: boolean }>("listFleetUsers", {}),
      accountCall<{ routes: { id: string; name: string }[] }>("listFleetRoutes", {}),
    ])
    setRoutes(available.routes)
    setUsers(result.users)
    setHasMore(result.hasMore)
  }, [])
  useEffect(() => {
    let active = true
    void reload()
      .catch((e) => {
        if (active) setError(accountError(e))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [reload])

  /** Uma alteração de cada vez evita envio duplicado; mensagens preservam falhas parciais. */
  const run = async (operation: () => Promise<unknown>, success: string) => {
    setBusy(true)
    setError("")
    setMessage("")
    try {
      await operation()
      setMessage(success)
      await reload()
    } catch (e) {
      setError(accountError(e))
    } finally {
      setBusy(false)
    }
  }
  const create = (event: FormEvent) => {
    event.preventDefault()
    void run(async () => {
      await accountCall("createDriver", { name: name.trim(), email: email.trim() })
      setName("")
      setEmail("")
    }, "Motorista criado. Envie as instruções para ele definir a própria senha.")
  }
  return (
    <section className="account-card">
      <h2>Minha equipe</h2>
      <p>Cadastre motoristas e gerencie apenas os vínculos da sua frota.</p>
      <form onSubmit={create}>
        <label>
          Nome do motorista
          <input required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          E-mail do motorista
          <input required type="email" maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <button className="primary-button" disabled={busy}>
          Cadastrar motorista
        </button>
      </form>
      {loading && <p role="status">Carregando equipe…</p>}
      {!loading && users.length === 0 && <p>Nenhum motorista cadastrado nesta frota.</p>}
      {hasMore && <p>Exibindo os primeiros 100 cadastros. Consulte a administração para acessar os demais.</p>}
      {users.map((user) => (
        <article className="account-member" key={user.id}>
          <h3>{user.name}</h3>
          <p>{user.email}</p>
          <p>
            {user.active ? "Ativo" : "Inativo"} · Rota: {user.routeId || "não atribuída"}
          </p>
          <div className="account-actions">
            <button
              className="secondary-button"
              disabled={busy}
              onClick={() =>
                void run(
                  () => accountCall("setDriverActive", { driverId: user.id, active: !user.active }),
                  "Situação do motorista atualizada.",
                )
              }
            >
              {user.active ? "Desativar" : "Reativar"}
            </button>
            <button
              className="secondary-button"
              disabled={busy || !user.email}
              onClick={() =>
                void run(
                  () => resetPassword(user.email),
                  "Instruções solicitadas. No emulador, consulte o link no console do Auth.",
                )
              }
            >
              Enviar definição de senha
            </button>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              void run(() => setDriverRoute(user.id, routeIds[user.id].trim()), "Rota atribuída.")
            }}
          >
            <label>
              Rota do motorista
              <select
                required
                value={routeIds[user.id] ?? ""}
                onChange={(e) => setRouteIds((prev) => ({ ...prev, [user.id]: e.target.value }))}
              >
                <option value="">Selecione uma rota</option>
                {routes.map((route) => (
                  <option key={route.id} value={route.id}>
                    {route.name}
                  </option>
                ))}
              </select>
            </label>
            <button className="secondary-button" disabled={busy || !routes.length}>
              Atribuir rota
            </button>
          </form>
        </article>
      ))}
      {error && (
        <p className="account-error" role="alert">
          {error}
          <button className="secondary-button" disabled={busy} onClick={() => void run(reload, "Equipe atualizada.")}>
            Tentar novamente
          </button>
        </p>
      )}
      {message && (
        <p className="account-success" role="status">
          {message}
        </p>
      )}
    </section>
  )
}
