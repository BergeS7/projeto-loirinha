import type { ReactNode } from "react"

type Props = {
  icon?: ReactNode
  title?: string
  description?: string
  variant?: "default" | "compact" | "large"
  /** Envolve o ícone num círculo de destaque. */
  highlightIcon?: boolean
  titleAs?: "h1" | "h3"
  children?: ReactNode
}

export default function EmptyState({ icon, title, description, variant = "default", highlightIcon, titleAs: Title = "h3", children }: Props) {
  return (
    <div className={`empty-state ${variant === "default" ? "" : variant}`}>
      {icon && (highlightIcon ? <span className="empty-illustration">{icon}</span> : icon)}
      {title && <Title>{title}</Title>}
      {description && <p>{description}</p>}
      {children}
    </div>
  )
}
