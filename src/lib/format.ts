/** Formatação de textos exibidos na tela e normalização para buscas. */
import type { Lotacao } from "../types/transit"

/** Texto exibido para cada nível de lotação do ônibus. */
export const LOTACAO_LABEL: Record<Lotacao, string> = {
  livre: "Lugares livres",
  moderado: "Lotação média",
  cheio: "Mais cheio",
}

/** Saudação conforme a hora do dia: "Bom dia", "Boa tarde" ou "Boa noite". */
export function saudacao(data = new Date()) {
  const hora = data.getHours()
  if (hora < 5) return "Boa noite"
  if (hora < 12) return "Bom dia"
  if (hora < 18) return "Boa tarde"
  return "Boa noite"
}

// Faixa Unicode dos acentos "soltos" que o NFD separa das letras (á vira a + ´).
const ACENTOS = new RegExp("[\\u0300-\\u036f]", "g")

/**
 * Prepara um texto para comparação em buscas: sem espaços nas pontas, minúsculo e sem acentos
 * ("Rodoviária" vira "rodoviaria").
 */
export function normalizarTexto(texto: string) {
  return texto.trim().toLocaleLowerCase("pt-BR").normalize("NFD").replace(ACENTOS, "")
}
