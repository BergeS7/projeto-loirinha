/** Botão de estrela para favoritar linhas e pontos. */
import { Star } from "lucide-react"

type Props = {
  active: boolean
  onClick: () => void
  label?: string
}

/** Estrela preenchida quando `active`. O texto para leitores de tela muda conforme o estado. */
export default function FavoriteButton({ active, onClick, label = "Favoritar" }: Props) {
  return (
    <button
      type="button"
      className={`icon-button ${active ? "favorite-active" : ""}`}
      onClick={onClick}
      aria-label={active ? "Remover dos favoritos" : label}
      aria-pressed={active}
    >
      <Star size={22} fill={active ? "currentColor" : "none"} />
    </button>
  )
}
