/** Cabeçalho padrão das telas internas. */
import { ArrowLeft } from "lucide-react"
import type { ReactNode } from "react"
import { useNavigate } from "react-router"
import { paths } from "../../app/paths"

type Props = {
  title: string
  subtitle?: string
  action?: ReactNode
}

/** Botão voltar, título, subtítulo e uma ação opcional à direita (ex.: favoritar). */
export default function PageHeader({ title, subtitle, action }: Props) {
  const navigate = useNavigate()
  // Quem abriu um link direto não tem histórico no app: volta para o mapa.
  const goBack = () => (window.history.state?.idx > 0 ? navigate(-1) : navigate(paths.home))

  return (
    <header className="page-header">
      <button type="button" className="icon-button" onClick={goBack} aria-label="Voltar">
        <ArrowLeft size={22} />
      </button>
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action && <div className="header-action">{action}</div>}
    </header>
  )
}
