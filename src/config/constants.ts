/** Constantes de comportamento do app. Ajuste aqui, em vez de espalhar números pelo código. */
import type { Coordenada } from "../types/transit"

/** Praça da Matriz, centro de Santa Inês (MA). */
export const CENTRO_SANTA_INES: Coordenada = [-3.65693, -45.37704]

/** Intervalos de atualização automática, em milissegundos. */
export const REFRESH_INTERVAL = {
  posicoesOnibus: 3_000,
  previsoes: 15_000,
} as const

/** Quantos pontos próximos a tela inicial busca. */
export const PONTOS_PROXIMOS_LIMITE = 6
/** Quantas buscas recentes ficam salvas no aparelho. */
export const BUSCAS_RECENTES_LIMITE = 5
/** Espera após a última tecla antes de buscar, para não fazer uma requisição por letra. */
export const BUSCA_DEBOUNCE_MS = 250

/** Velocidade média de caminhada usada para estimar o tempo até o ponto. */
export const VELOCIDADE_CAMINHADA_KMH = 4.8

/**
 * Chaves usadas no localStorage. Mudar um valor faz o app "esquecer" o que o usuário já tinha
 * salvo.
 */
export const STORAGE_KEYS = {
  favoritos: "loirinha:favorites",
  buscasRecentes: "loirinha:recent-searches",
} as const
