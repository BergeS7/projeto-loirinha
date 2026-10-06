import { useCallback, useEffect, useState } from "react"
import { FAVORITOS_EVENT, type TipoFavorito, alternarFavorito, getFavoritos } from "../services/preferences"

export default function useFavorites() {
  const [favorites, setFavorites] = useState(getFavoritos)

  useEffect(() => {
    const update = () => setFavorites(getFavoritos())
    window.addEventListener(FAVORITOS_EVENT, update)
    // Mantém abas diferentes sincronizadas.
    window.addEventListener("storage", update)
    return () => {
      window.removeEventListener(FAVORITOS_EVENT, update)
      window.removeEventListener("storage", update)
    }
  }, [])

  const toggle = useCallback((tipo: TipoFavorito, id: string) => {
    setFavorites(alternarFavorito(tipo, id))
  }, [])

  const isFavorite = useCallback((tipo: TipoFavorito, id: string) => favorites[tipo].includes(id), [favorites])

  return { favorites, toggle, isFavorite }
}
