/** Implementação do TransitService que conversa com o backend real por HTTP. */
import { HttpError, http } from "../../lib/http"
import type { Aviso, Coordenada, Linha, Onibus, Ponto, PontoProximo, Previsao, ResultadoBusca } from "../../types/transit"
import type { TransitService } from "./TransitService"

/** Converte 404 em `null`, para "não encontrado" não virar erro na tela. */
async function orNull<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise
  } catch (error) {
    if (error instanceof HttpError && error.status === 404) return null
    throw error
  }
}

/**
 * Implementação HTTP. Os endpoints e formatos estão documentados em docs/API.md.
 * Se o backend usar outro formato, faça a conversão aqui: as telas não mudam.
 */
export const apiTransitService: TransitService = {
  getLinhas: ({ signal } = {}) => http.get<Linha[]>("/linhas", { signal }),
  getLinha: (id, { signal } = {}) => orNull(http.get<Linha>(`/linhas/${encodeURIComponent(id)}`, { signal })),
  getItinerario: (linhaId, { signal } = {}) => http.get<Ponto[]>(`/linhas/${encodeURIComponent(linhaId)}/itinerario`, { signal }),
  getTracado: async (linhaId, { signal } = {}) =>
    (await orNull(http.get<Coordenada[]>(`/linhas/${encodeURIComponent(linhaId)}/tracado`, { signal }))) ?? [],

  getPontos: ({ signal } = {}) => http.get<Ponto[]>("/pontos", { signal }),
  getPonto: (id, { signal } = {}) => orNull(http.get<Ponto>(`/pontos/${encodeURIComponent(id)}`, { signal })),
  getPontosProximos: ([lat, lng], limite, { signal } = {}) =>
    http.get<PontoProximo[]>("/pontos/proximos", { query: { lat, lng, limite }, signal }),
  getPrevisoes: (pontoId, { signal } = {}) => http.get<Previsao[]>(`/pontos/${encodeURIComponent(pontoId)}/previsoes`, { signal }),

  getOnibus: (linhaId, { signal } = {}) => http.get<Onibus[]>("/onibus", { query: { linhaId }, signal }),

  getAvisos: ({ signal } = {}) => http.get<Aviso[]>("/avisos", { signal }),
  buscar: (termo, { signal } = {}) => http.get<ResultadoBusca>("/busca", { query: { q: termo }, signal }),
}
