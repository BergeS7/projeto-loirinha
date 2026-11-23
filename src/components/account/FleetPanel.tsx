/**
 * Área do dono de frota, usando só o que o backend original permite:
 * - leitura direta (Firestore) de buses, drivers e routes da própria frota
 *   (as consultas filtram por fleet_owner_id == uid, como as regras exigem);
 * - callables createRoute, setDriverRoute e getBusRoute;
 * - telemetria ao vivo dos ônibus da frota.
 *
 * O backend não tem function para cadastrar, ativar ou desativar motoristas e ônibus: isso continua
 * sendo feito pela administração (scripts do backend).
 */
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react"
import { collection, getDocs, query, where } from "firebase/firestore"
import { getFirebase } from "../../config/firebase"
import { accountError } from "../../services/backend/accounts"
import { createRoute, getBusRoute, setDriverRoute } from "../../services/backend/functions"
import type { BusDoc, Route, RouteBody, RouteStop } from "../../types/backend"
import LiveBusesPanel from "./LiveBusesPanel"

type DriverDoc = { user_id: string; fleet_owner_id: string; driver_code?: string; active: boolean; id_route?: string }
type FleetData = {
  buses: (BusDoc & { id: string })[]
  drivers: (DriverDoc & { id: string })[]
  routes: (RouteBody & { id: string })[]
}

const EMPTY: FleetData = { buses: [], drivers: [], routes: [] }

/** Lê "Nome; latitude; longitude" (uma parada por linha). */
function parseStops(text: string): RouteStop[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, i) => {
      const [name, lat, lng] = line.split(";").map((part) => part.trim())
      return { name, latitude: Number(lat), longitude: Number(lng), order: i + 1 }
    })
}

export default function FleetPanel() {
  const [data, setData] = useState<FleetData>(EMPTY)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [routeChoice, setRouteChoice] = useState<Record<string, string>>({})
  const [busRoutes, setBusRoutes] = useState<Record<string, Route | string>>({})
  const [form, setForm] = useState({
    name: "",
    originName: "",
    originLat: "",
    originLng: "",
    destName: "",
    destLat: "",
    destLng: "",
    stops: "",
    color: "#1E88E5",
    colorOut: "#FF6D00",
  })

  const reload = useCallback(async () => {
    const { db, auth } = getFirebase()
    const uid = auth.currentUser!.uid
    const mine = (name: string) => getDocs(query(collection(db, name), where("fleet_owner_id", "==", uid)))
    const [buses, drivers, routes] = await Promise.all([mine("buses"), mine("drivers"), mine("routes")])
    setData({
      buses: buses.docs.map((d) => ({ id: d.id, ...(d.data() as BusDoc) })),
      drivers: drivers.docs.map((d) => ({ id: d.id, ...(d.data() as DriverDoc) })),
      routes: routes.docs.map((d) => ({ id: d.id, ...(d.data() as RouteBody) })),
    })
  }, [])

  useEffect(() => {
    let active = true
    void reload()
      .catch((e) => active && setError(accountError(e)))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [reload])

  /** Uma operação de cada vez evita envio duplicado. */
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

  const routeName = (id?: string) => (id ? (data.routes.find((r) => r.id === id)?.name ?? id) : "não atribuída")
  const driverOf = (uid: string | null) => data.drivers.find((d) => d.user_id === uid)
  const busIds = useMemo(() => data.buses.map((b) => b.id), [data.buses])

  const submitRoute = (event: FormEvent) => {
    event.preventDefault()
    void run(async () => {
      await createRoute({
        name: form.name.trim(),
        origin: { name: form.originName.trim(), latitude: Number(form.originLat), longitude: Number(form.originLng) },
        destination: { name: form.destName.trim(), latitude: Number(form.destLat), longitude: Number(form.destLng) },
        stops: parseStops(form.stops),
        color_hex_route: form.color.toUpperCase(),
        color_hex_out_route: form.colorOut.toUpperCase(),
      })
      setForm((f) => ({ ...f, name: "", originName: "", originLat: "", originLng: "", destName: "", destLat: "", destLng: "", stops: "" }))
    }, "Rota cadastrada.")
  }

  const field = (key: keyof typeof form) => ({
    value: form[key],
    onChange: (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value })),
  })

  return (
    <>
      <section className="account-card">
        <h2>Minha frota</h2>
        {loading && <p role="status">Carregando frota…</p>}

        <h3>Ônibus</h3>
        {!loading && data.buses.length === 0 && <p>Nenhum ônibus nesta frota.</p>}
        {data.buses.map((bus) => {
          const driver = driverOf(bus.active_driver_id)
          const route = busRoutes[bus.id]
          return (
            <article className="account-member" key={bus.id}>
              <h3>
                {bus.plate ?? bus.id} <small>· {bus.tag_code}</small>
              </h3>
              <p>
                {bus.model ?? "Modelo não informado"}
                {bus.capacity ? ` · ${bus.capacity} lugares` : ""}
              </p>
              <p>
                {bus.active_driver_id
                  ? `Em uso por ${driver?.driver_code ?? "motorista de outra frota ou sem cadastro"}`
                  : "Livre"}
              </p>
              {bus.active_driver_id && (
                <button
                  className="secondary-button"
                  disabled={busy}
                  onClick={async () => {
                    try {
                      const result = await getBusRoute(bus.id)
                      setBusRoutes((prev) => ({ ...prev, [bus.id]: result.route }))
                    } catch (e) {
                      setBusRoutes((prev) => ({ ...prev, [bus.id]: accountError(e) }))
                    }
                  }}
                >
                  Ver rota em andamento
                </button>
              )}
              {typeof route === "string" && <p>{route}</p>}
              {route && typeof route !== "string" && (
                <p>
                  Rota: <strong>{route.name}</strong> ({route.origin.name} → {route.destination.name},{" "}
                  {route.stops.length} paradas)
                </p>
              )}
            </article>
          )
        })}

        <h3>Motoristas</h3>
        {!loading && data.drivers.length === 0 && <p>Nenhum motorista nesta frota.</p>}
        {data.drivers.map((driver) => (
          <article className="account-member" key={driver.id}>
            <h3>{driver.driver_code ?? driver.id}</h3>
            <p>
              {driver.active ? "Ativo" : "Inativo"} · Rota: {routeName(driver.id_route)}
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                void run(() => setDriverRoute(driver.id, routeChoice[driver.id]), "Rota atribuída.")
              }}
            >
              <label>
                Rota do motorista
                <select
                  required
                  value={routeChoice[driver.id] ?? ""}
                  onChange={(e) => setRouteChoice((prev) => ({ ...prev, [driver.id]: e.target.value }))}
                >
                  <option value="">Selecione uma rota</option>
                  {data.routes.map((route) => (
                    <option key={route.id} value={route.id}>
                      {route.name}
                    </option>
                  ))}
                </select>
              </label>
              <button className="secondary-button" disabled={busy || !data.routes.length}>
                Atribuir rota
              </button>
            </form>
          </article>
        ))}
        <p>Cadastrar, ativar ou desativar motoristas e ônibus ainda é feito pela administração.</p>

        <h3>Rotas</h3>
        {!loading && data.routes.length === 0 && <p>Nenhuma rota cadastrada.</p>}
        <ul className="live-list">
          {data.routes.map((route) => (
            <li key={route.id}>
              <span className="route-swatch" style={{ background: route.color_hex_route }} aria-hidden />
              <strong>{route.name}</strong>
              <small>
                {route.origin?.name} → {route.destination?.name} · {route.stops?.length ?? 0} paradas
              </small>
            </li>
          ))}
        </ul>

        <form onSubmit={submitRoute}>
          <h3>Nova rota</h3>
          <label>
            Nome da rota
            <input required maxLength={120} {...field("name")} />
          </label>
          <div className="form-row">
            <label>
              Origem
              <input required placeholder="Terminal Central" {...field("originName")} />
            </label>
            <label>
              Latitude
              <input required inputMode="decimal" placeholder="-3.668" {...field("originLat")} />
            </label>
            <label>
              Longitude
              <input required inputMode="decimal" placeholder="-45.381" {...field("originLng")} />
            </label>
          </div>
          <div className="form-row">
            <label>
              Destino
              <input required placeholder="Terminal Rodoviário" {...field("destName")} />
            </label>
            <label>
              Latitude
              <input required inputMode="decimal" placeholder="-3.674" {...field("destLat")} />
            </label>
            <label>
              Longitude
              <input required inputMode="decimal" placeholder="-45.389" {...field("destLng")} />
            </label>
          </div>
          <label>
            Paradas (uma por linha: nome; latitude; longitude)
            <textarea rows={4} placeholder={"Praça Central; -3.669; -45.383\nHospital; -3.671; -45.385"} {...field("stops")} />
          </label>
          <div className="form-row">
            <label>
              Cor da rota
              <input type="color" {...field("color")} />
            </label>
            <label>
              Cor de desvio
              <input type="color" {...field("colorOut")} />
            </label>
          </div>
          <button className="primary-button" disabled={busy}>
            Cadastrar rota
          </button>
        </form>

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
      </section>
      {!loading && <LiveBusesPanel busIds={busIds} title="Ônibus da frota ao vivo" />}
    </>
  )
}
