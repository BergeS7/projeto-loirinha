import { PONTOS_PROXIMOS_LIMITE, REFRESH_INTERVAL } from "../config/constants"
import { transitService } from "../services/transit"
import type { Coordenada } from "../types/transit"
import useAsyncData from "./useAsyncData"

/** Hooks de dados de transporte. São a única porta de entrada das telas para o backend. */

export function useLinhas() {
  return useAsyncData((signal) => transitService.getLinhas({ signal }), [])
}

export function useLinha(id: string) {
  return useAsyncData((signal) => transitService.getLinha(id, { signal }), [id])
}

export function useItinerario(linhaId: string) {
  return useAsyncData((signal) => transitService.getItinerario(linhaId, { signal }), [linhaId])
}

export function useTracado(linhaId: string) {
  return useAsyncData((signal) => transitService.getTracado(linhaId, { signal }), [linhaId])
}

/** Traçados de várias linhas, por id. Usado para manter os ônibus sobre as ruas no mapa geral. */
export function useTracados(linhaIds: string[]) {
  const chave = [...linhaIds].sort().join(",")
  return useAsyncData(
    linhaIds.length > 0
      ? async (signal) => {
          const tracados = await Promise.all(linhaIds.map((id) => transitService.getTracado(id, { signal })))
          return Object.fromEntries(linhaIds.map((id, i) => [id, tracados[i]])) as Record<string, Coordenada[]>
        }
      : null,
    [chave],
  )
}

export function usePontos() {
  return useAsyncData((signal) => transitService.getPontos({ signal }), [])
}

export function usePonto(id: string) {
  return useAsyncData((signal) => transitService.getPonto(id, { signal }), [id])
}

/** Sem posição (`undefined`), não carrega nada. */
export function usePontosProximos(posicao: Coordenada | undefined, limite = PONTOS_PROXIMOS_LIMITE) {
  const [lat, lng] = posicao ?? []
  return useAsyncData(
    posicao ? (signal) => transitService.getPontosProximos(posicao, limite, { signal }) : null,
    [lat, lng, limite],
  )
}

export function usePrevisoes(pontoId: string) {
  return useAsyncData((signal) => transitService.getPrevisoes(pontoId, { signal }), [pontoId], {
    refreshInterval: REFRESH_INTERVAL.previsoes,
  })
}

export function useAvisos() {
  return useAsyncData((signal) => transitService.getAvisos({ signal }), [])
}

/** Termo vazio não dispara busca. */
export function useBusca(termo: string) {
  const busca = termo.trim()
  return useAsyncData(busca ? (signal) => transitService.buscar(busca, { signal }) : null, [busca])
}

/** Posições dos ônibus, atualizadas automaticamente. */
export function useBusPositions(linhaId?: string) {
  const { data } = useAsyncData((signal) => transitService.getOnibus(linhaId, { signal }), [linhaId], {
    refreshInterval: REFRESH_INTERVAL.posicoesOnibus,
  })
  return data ?? []
}
