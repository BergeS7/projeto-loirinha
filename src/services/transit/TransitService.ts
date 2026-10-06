/** Contrato (interface) da camada de dados de transporte. */
import type { Aviso, Coordenada, Linha, Onibus, Ponto, PontoProximo, Previsao, ResultadoBusca } from "../../types/transit"

/** Opções comuns a todas as chamadas. `signal` permite cancelar a requisição. */
export type CallOptions = { signal?: AbortSignal }

/**
 * Contrato entre as telas e a fonte de dados.
 * As telas nunca acessam dados diretamente: elas usam os hooks de `src/hooks/transit.ts`,
 * que chamam uma implementação deste contrato (simulada ou HTTP).
 */
export interface TransitService {
  getLinhas(options?: CallOptions): Promise<Linha[]>
  /** Retorna `null` quando a linha não existe. */
  getLinha(id: string, options?: CallOptions): Promise<Linha | null>
  /** Pontos do itinerário da linha, na ordem do percurso. */
  getItinerario(linhaId: string, options?: CallOptions): Promise<Ponto[]>
  /**
   * Traçado da linha pelas ruas, na ordem do percurso, passando pelos pontos.
   * Vazio quando a linha não existe ou não tem traçado.
   */
  getTracado(linhaId: string, options?: CallOptions): Promise<Coordenada[]>

  getPontos(options?: CallOptions): Promise<Ponto[]>
  /** Retorna `null` quando o ponto não existe. */
  getPonto(id: string, options?: CallOptions): Promise<Ponto | null>
  getPontosProximos(posicao: Coordenada, limite: number, options?: CallOptions): Promise<PontoProximo[]>
  getPrevisoes(pontoId: string, options?: CallOptions): Promise<Previsao[]>

  /** Posição atual dos ônibus. Sem `linhaId`, retorna todos. */
  getOnibus(linhaId?: string, options?: CallOptions): Promise<Onibus[]>

  getAvisos(options?: CallOptions): Promise<Aviso[]>
  buscar(termo: string, options?: CallOptions): Promise<ResultadoBusca>
}
