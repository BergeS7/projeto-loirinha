/**
 * Ônibus em serviço, ao vivo, a partir do backend original:
 * - posição em /telemetry (RTDB, leitura para qualquer usuário logado);
 * - placa e modelo em buses/{busId} (Firestore, leitura para qualquer usuário logado).
 *
 * O backend não expõe linhas para passageiros (as rotas com frota só são lidas pelo dono), então
 * aqui aparecem só a posição, a velocidade, o estado e a última atualização de cada ônibus.
 */
import { useEffect, useMemo, useState } from "react"
import { doc, getDoc } from "firebase/firestore"
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet"
import { onValue, ref } from "firebase/database"
import { getFirebase } from "../../config/firebase"
import { subscribeTelemetry, type TelemetrySnapshot } from "../../services/backend/telemetry"
import { accountError } from "../../services/backend/accounts"
import type { BusDoc, TelemetryStatus } from "../../types/backend"

/** Mesma regra do backend (telemetry.py): sem envio por mais de 45 s = perda de conexão. */
const OFFLINE_MS = 45_000

const CENTRO_SANTA_INES: [number, number] = [-3.6667, -45.38]

const STATUS_LABEL: Record<TelemetryStatus, string> = {
  in_service: "Em serviço",
  delayed: "Atrasado",
  out_of_route: "Fora da rota",
}

type Props = {
  /** Mostra só estes ônibus (ex.: os da frota do dono). Sem filtro, mostra todos. */
  busIds?: string[]
  title?: string
}

/** "há 12 s", "há 3 min". */
function age(ms: number, now: number) {
  const s = Math.max(0, Math.round((now - ms) / 1000))
  return s < 60 ? `há ${s} s` : `há ${Math.round(s / 60)} min`
}

export default function LiveBusesPanel({ busIds, title = "Ônibus ao vivo" }: Props) {
  const [telemetry, setTelemetry] = useState<TelemetrySnapshot>({})
  const [buses, setBuses] = useState<Record<string, BusDoc | null>>({})
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState("")
  const [now, setNow] = useState(() => Date.now())
  // Diferença entre o relógio do aparelho e o do servidor (updated_at é hora do servidor).
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    let stop = () => {}
    try {
      stop = subscribeTelemetry(
        (data) => {
          setTelemetry(data)
          setLoaded(true)
          setError("")
        },
        (e) => setError(accountError(e)),
      )
    } catch (e) {
      setError(accountError(e))
    }
    let stopOffset = () => {}
    try {
      stopOffset = onValue(ref(getFirebase().rtdb, ".info/serverTimeOffset"), (snap) => setOffset(Number(snap.val()) || 0))
    } catch {
      // Sem Firebase configurado: o erro já aparece pela assinatura da telemetria.
    }
    const timer = window.setInterval(() => setNow(Date.now()), 5000)
    return () => {
      stop()
      stopOffset()
      window.clearInterval(timer)
    }
  }, [])

  const visible = useMemo(
    () =>
      Object.entries(telemetry)
        .filter(([, node]) => node && Number.isFinite(node.lat) && Number.isFinite(node.lng))
        .filter(([id]) => !busIds || busIds.includes(id))
        .sort(([a], [b]) => a.localeCompare(b)),
    [telemetry, busIds],
  )

  const serverNow = now + offset
  /** Online só se o backend diz que está e o último envio tem até 45 s (o monitor pode estar parado). */
  const online = (node: { is_online: boolean; updated_at: number }) =>
    node.is_online && serverNow - node.updated_at <= OFFLINE_MS

  // Busca placa/modelo uma vez por ônibus que aparecer na telemetria.
  useEffect(() => {
    const missing = visible.map(([id]) => id).filter((id) => !(id in buses))
    if (!missing.length) return
    let active = true
    const { db } = getFirebase()
    void Promise.all(
      missing.map(async (id) => {
        try {
          const snap = await getDoc(doc(db, "buses", id))
          return [id, snap.exists() ? (snap.data() as BusDoc) : null] as const
        } catch {
          return [id, null] as const
        }
      }),
    ).then((entries) => {
      if (active) setBuses((prev) => ({ ...prev, ...Object.fromEntries(entries) }))
    })
    return () => {
      active = false
    }
  }, [visible, buses])

  return (
    <section className="account-card">
      <h2>{title}</h2>
      <p>Posição enviada pelo celular de cada ônibus, atualizada a cada 15 a 20 segundos.</p>
      <div className="live-map">
        <MapContainer center={CENTRO_SANTA_INES} zoom={14} scrollWheelZoom={false} style={{ height: "100%" }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {visible.map(([id, node]) => (
            <CircleMarker
              key={id}
              center={[node.lat, node.lng]}
              radius={9}
              pathOptions={{
                color: "#181a1f",
                weight: 2,
                fillColor: online(node) ? "#f5b800" : "#9aa0a8",
                fillOpacity: 0.95,
              }}
            >
              <Tooltip>
                {buses[id]?.plate ?? id} · {online(node) ? `${node.speed} km/h` : "sem sinal"}
              </Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
      {!loaded && !error && <p role="status">Conectando…</p>}
      {loaded && visible.length === 0 && <p>Nenhum ônibus em serviço agora.</p>}
      <ul className="live-list">
        {visible.map(([id, node]) => (
          <li key={id}>
            <strong>{buses[id]?.plate ?? id}</strong>
            {buses[id]?.model && <span> · {buses[id]?.model}</span>}
            <span className={online(node) ? "live-ok" : "live-lost"}>
              {online(node) ? STATUS_LABEL[node.status] ?? node.status : "Sem sinal"}
            </span>
            <small>
              {node.speed} km/h · atualizado {age(node.updated_at, serverNow)}
            </small>
          </li>
        ))}
      </ul>
      {error && (
        <p className="account-error" role="alert">
          {error}
        </p>
      )}
    </section>
  )
}
