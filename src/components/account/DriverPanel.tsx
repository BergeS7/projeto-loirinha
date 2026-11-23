/** Operação do motorista: check-in, rota e GPS explicitamente iniciado pelo titular. */
import { useEffect, useRef, useState } from "react"
import { collection, getDocs, query, where } from "firebase/firestore"
import { getFirebase } from "../../config/firebase"
import { checkIn, checkOut, endTelemetry, getMyRoute, sendTelemetry } from "../../services/backend/functions"
import { accountError } from "../../services/backend/accounts"
import { BackendError } from "../../services/backend/errors"
import type { Route } from "../../types/backend"

export default function DriverPanel() {
  const [tag, setTag] = useState("")
  const [busId, setBusId] = useState("")
  const [route, setRoute] = useState<Route>()
  const [busy, setBusy] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const generation = useRef(0)
  useEffect(() => {
    let active = true
    const { db, auth } = getFirebase()
    void getDocs(query(collection(db, "buses"), where("active_driver_id", "==", auth.currentUser!.uid)))
      .then((result) => {
        if (active) setBusId(result.docs[0]?.id ?? "")
      })
      .catch((e) => {
        if (active) setError(accountError(e))
      })
    void getMyRoute()
      .then((result) => {
        if (active) setRoute(result.route)
      })
      .catch((e) => {
        if (active) setMessage(accountError(e))
      })
    return () => {
      active = false
    }
  }, [])

  /** Limpa GPS e intervalo ao sair; nunca transmite localização sem o botão de iniciar. */
  useEffect(() => {
    if (!running || !busId) return
    if (!navigator.geolocation) {
      setError("GPS indisponível neste dispositivo.")
      setRunning(false)
      return
    }
    const version = ++generation.current
    let latest: GeolocationPosition | undefined
    let sending = false
    let lastSent = 0
    const transmit = async () => {
      if (
        version !== generation.current ||
        sending ||
        !latest ||
        Date.now() - latest.timestamp > 45_000 ||
        Date.now() - lastSent < 15_000
      )
        return
      sending = true
      lastSent = Date.now()
      const fix = latest
      try {
        await sendTelemetry({
          busId,
          lat: fix.coords.latitude,
          lng: fix.coords.longitude,
          speed: Math.max(0, (fix.coords.speed ?? 0) * 3.6),
          heading: Math.max(0, Math.min(359, fix.coords.heading ?? 0)),
          status: "in_service",
          captured_at: fix.timestamp,
        })
        if (version === generation.current) setMessage("Posição enviada. Mantenha esta tela aberta durante o serviço.")
      } catch (e) {
        if (version === generation.current) setError(accountError(e))
      } finally {
        sending = false
      }
    }
    const watch = navigator.geolocation.watchPosition(
      (fix) => {
        latest = fix
        void transmit()
      },
      () => {
        if (version === generation.current) {
          setError("Não foi possível acessar o GPS. Confira a permissão e tente novamente.")
          setRunning(false)
        }
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 },
    )
    const timer = window.setInterval(() => void transmit(), 15000)
    return () => {
      generation.current++
      navigator.geolocation.clearWatch(watch)
      window.clearInterval(timer)
    }
  }, [running, busId])

  return (
    <section className="account-card">
      <h2>Minha operação</h2>
      <p>Ônibus atual: {busId || "nenhum"}</p>
      <form
        onSubmit={async (e) => {
          e.preventDefault()
          setBusy(true)
          setError("")
          try {
            const result = await checkIn(tag.trim())
            setBusId(result.busId)
            setMessage("Check-in realizado.")
          } catch (e) {
            setError(accountError(e))
          } finally {
            setBusy(false)
          }
        }}
      >
        <label>
          Tag do ônibus
          <input required maxLength={128} value={tag} onChange={(e) => setTag(e.target.value)} />
        </label>
        <button className="primary-button" disabled={busy || running}>
          Fazer check-in
        </button>
      </form>
      <div className="account-actions">
        <button
          className="secondary-button"
          disabled={!busId || busy}
          onClick={() => {
            setError("")
            setRunning((value) => !value)
          }}
        >
          {running ? "Pausar envio de GPS" : "Iniciar envio de GPS"}
        </button>
        <button
          className="secondary-button"
          disabled={busy}
          onClick={async () => {
            generation.current++
            setRunning(false)
            setBusy(true)
            setError("")
            try {
              if (busId) {
                try {
                  await endTelemetry(busId)
                } catch (error) {
                  // Desativação bloqueia GPS, mas não pode prender o ônibus ao motorista.
                  // O monitor remove o nó após o check-out; erros de rede continuam visíveis.
                  if (
                    !(error instanceof BackendError) ||
                    !["driver_inactive", "driver_record_not_found"].includes(error.reason)
                  )
                    throw error
                }
              }
              await checkOut()
              setBusId("")
              setMessage("Expediente encerrado.")
            } catch (e) {
              setError(accountError(e))
            } finally {
              setBusy(false)
            }
          }}
        >
          Encerrar expediente
        </button>
      </div>
      <p>
        O GPS é enviado a cada 15 segundos. Ao pausar ou sair da tela, o envio para; para liberar o veículo, encerre o
        expediente antes de sair da conta.
      </p>
      <h3>Minha rota</h3>
      {route ? (
        <>
          <p>{route.name}</p>
          <ol>
            {[...route.stops]
              .sort((a, b) => a.order - b.order)
              .map((stop) => (
                <li key={stop.order}>{stop.name}</li>
              ))}
          </ol>
        </>
      ) : (
        <p>Nenhuma rota disponível. Consulte o dono da frota.</p>
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
    </section>
  )
}
