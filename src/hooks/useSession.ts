/** Estado de conta isolado das telas públicas: não inicializa Firebase no modo demonstração. */
import { useEffect, useState } from "react"
import { onIdTokenChanged, type User } from "firebase/auth"
import { getFirebase } from "../config/firebase"
import type { Role } from "../types/backend"

export default function useSession() {
  const [state, setState] = useState<{ loading: boolean; user: User | null; role: Role | null; error?: unknown }>({
    loading: true,
    user: null,
    role: null,
  })
  useEffect(() => {
    let active = true
    let version = 0
    let stop = () => {}
    try {
      stop = onIdTokenChanged(
        getFirebase().auth,
        async (user) => {
          const current = ++version
          try {
            const raw = user ? (await user.getIdTokenResult()).claims.role : null
            const role = ["motorista", "dono_frota", "passageiro"].includes(String(raw)) ? (raw as Role) : null
            if (active && current === version) setState({ user, role, loading: false })
          } catch (error) {
            if (active && current === version) setState({ user, role: null, loading: false, error })
          }
        },
        (error) => {
          if (active) setState({ user: null, role: null, loading: false, error })
        },
      )
    } catch (error) {
      setState({ user: null, role: null, loading: false, error })
    }
    return () => {
      active = false
      version++
      stop()
    }
  }, [])
  return state
}
