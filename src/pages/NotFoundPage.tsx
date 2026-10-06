/** Tela de endereço inexistente (qualquer rota não mapeada). */
import { MapPinOff } from "lucide-react"
import { Link } from "react-router"
import { paths } from "../app/paths"
import EmptyState from "../components/ui/EmptyState"

/** Mensagem amigável com atalho de volta ao mapa. */
export default function NotFoundPage() {
  return (
    <div className="page">
      <EmptyState
        variant="large"
        titleAs="h1"
        icon={<MapPinOff size={38} />}
        title="Essa parada não existe"
        description="Volte ao mapa para continuar sua viagem."
      >
        <Link to={paths.home} className="primary-button">
          Voltar ao mapa
        </Link>
      </EmptyState>
    </div>
  )
}
