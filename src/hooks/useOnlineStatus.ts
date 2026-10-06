/** Hook que acompanha a conexão com a internet. */
import { useEffect, useState } from "react"

/** `true` enquanto o aparelho tem internet. Atualiza sozinho ao conectar ou desconectar. */
export default function useOnlineStatus() {
  const [online, setOnline] = useState(navigator.onLine)

  useEffect(() => {
    const update = () => setOnline(navigator.onLine)
    window.addEventListener("online", update)
    window.addEventListener("offline", update)
    return () => {
      window.removeEventListener("online", update)
      window.removeEventListener("offline", update)
    }
  }, [])

  return online
}
