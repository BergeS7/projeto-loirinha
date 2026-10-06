import type { LinhaResumo } from "../../types/transit"

export default function RouteBadge({ linha }: { linha: Pick<LinhaResumo, "numero" | "cor"> }) {
  return (
    <span className="route-badge" style={{ backgroundColor: linha.cor }}>
      {linha.numero}
    </span>
  )
}
