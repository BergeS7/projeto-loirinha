/** Caminhos das telas. Use estes helpers em vez de montar URLs à mão. */
export const paths = {
  home: "/",
  buscar: "/buscar",
  favoritos: "/favoritos",
  avisos: "/avisos",
  ponto: (id: string) => `/ponto/${encodeURIComponent(id)}`,
  linha: (id: string) => `/linha/${encodeURIComponent(id)}`,
  acompanhar: (linhaId: string, onibusId: string) =>
    `/acompanhar/${encodeURIComponent(linhaId)}/${encodeURIComponent(onibusId)}`,
} as const
