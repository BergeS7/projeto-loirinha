import type { Lotacao } from "../types/transit"

export const LOTACAO_LABEL: Record<Lotacao, string> = {
  livre: "Lugares livres",
  moderado: "Lotação média",
  cheio: "Mais cheio",
}

export function saudacao(data = new Date()) {
  const hora = data.getHours()
  if (hora < 5) return "Boa noite"
  if (hora < 12) return "Bom dia"
  if (hora < 18) return "Boa tarde"
  return "Boa noite"
}

export function normalizarTexto(texto: string) {
  return texto
    .trim()
    .toLocaleLowerCase("pt-BR")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
}
