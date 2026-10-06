/** Raiz do React: entrega toda a navegação ao React Router. */
import { RouterProvider } from "react-router"
import { router } from "./routes"

/** Componente raiz. As telas e a navegação são definidas em ./routes. */
export default function App() {
  return <RouterProvider router={router} />
}
