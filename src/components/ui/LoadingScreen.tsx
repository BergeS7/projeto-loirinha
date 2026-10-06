/** Indicador de carregamento de tela inteira. */
export default function LoadingScreen({ label = "Carregando..." }: { label?: string }) {
  return (
    <div className="loading-screen" role="status">
      <span className="loader" />
      <p>{label}</p>
    </div>
  )
}
