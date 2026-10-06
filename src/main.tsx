/**
 * Ponto de entrada do app: carrega os estilos globais (incluindo o CSS do Leaflet, usado pelos
 * mapas) e monta o <App /> na div #root do index.html.
 */
import React from "react"
import ReactDOM from "react-dom/client"
import App from "./app/App"
import "./index.css"
import "leaflet/dist/leaflet.css"

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
