/** Selo com o número da linha. */
import type { LinhaResumo } from "../../types/transit"

/** Número da linha num selo com a cor da linha. */
export default function RouteBadge({ linha }: { linha: Pick<LinhaResumo, "numero" | "cor"> }) {
  return (
    <span className="route-badge" style={{ backgroundColor: linha.cor }}>
      {linha.numero}
    </span>
  )
}
