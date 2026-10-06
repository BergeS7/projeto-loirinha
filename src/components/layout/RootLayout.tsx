/**
 * Moldura comum a todas as telas: aviso de sem internet, área de conteúdo (<Outlet />) e navegação
 * principal. No celular a navegação fica embaixo; em telas largas vira um menu lateral com a logo
 * (veja styles/responsive.css).
 */
import { Bell, Heart, Map, Search } from "lucide-react"
import { NavLink, Outlet } from "react-router"
import { paths } from "../../app/paths"
import BrandLogo from "../ui/BrandLogo"
import useOnlineStatus from "../../hooks/useOnlineStatus"

const navItems = [
  { to: paths.home, label: "Mapa", icon: Map },
  { to: paths.buscar, label: "Buscar", icon: Search },
  { to: paths.favoritos, label: "Favoritos", icon: Heart },
  { to: paths.avisos, label: "Avisos", icon: Bell },
]

/** Layout raiz usado por todas as rotas. */
export default function RootLayout() {
  const online = useOnlineStatus()

  return (
    <div className="app-shell">
      {!online && (
        <div className="offline-banner" role="status">
          Você está sem internet. Mostrando os últimos dados carregados.
        </div>
      )}
      <main className="app-content" id="conteudo">
        <Outlet />
      </main>
      <nav className="main-nav" aria-label="Navegação principal">
        <div className="brand-lockup">
          <BrandLogo />
          <span>
            <strong>Loirinha</strong>
            <small>Santa Inês</small>
          </span>
        </div>
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} end={to === paths.home} className={({ isActive }) => (isActive ? "active" : "")}>
            <Icon size={21} strokeWidth={2.2} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
