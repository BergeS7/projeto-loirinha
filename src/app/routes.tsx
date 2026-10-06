import { lazy, Suspense } from "react"
import { createBrowserRouter } from "react-router"
import RootLayout from "../components/layout/RootLayout"
import LoadingScreen from "../components/ui/LoadingScreen"

const HomePage = lazy(() => import("../pages/HomePage"))
const SearchPage = lazy(() => import("../pages/SearchPage"))
const StopDetailPage = lazy(() => import("../pages/StopDetailPage"))
const LineDetailPage = lazy(() => import("../pages/LineDetailPage"))
const TrackBusPage = lazy(() => import("../pages/TrackBusPage"))
const FavoritesPage = lazy(() => import("../pages/FavoritesPage"))
const NoticesPage = lazy(() => import("../pages/NoticesPage"))
const NotFoundPage = lazy(() => import("../pages/NotFoundPage"))

const page = (Component: React.LazyExoticComponent<React.ComponentType>) => (
  <Suspense fallback={<LoadingScreen />}>
    <Component />
  </Suspense>
)

export const router = createBrowserRouter(
  [
    {
      path: "/",
      Component: RootLayout,
      children: [
        { index: true, element: page(HomePage) },
        { path: "buscar", element: page(SearchPage) },
        { path: "ponto/:id", element: page(StopDetailPage) },
        { path: "linha/:id", element: page(LineDetailPage) },
        { path: "acompanhar/:linhaId/:onibusId", element: page(TrackBusPage) },
        { path: "favoritos", element: page(FavoritesPage) },
        { path: "avisos", element: page(NoticesPage) },
        { path: "*", element: page(NotFoundPage) },
      ],
    },
  ],
  { basename: import.meta.env.BASE_URL },
)
