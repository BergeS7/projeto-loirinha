import type { Aviso, Coordenada, Linha, Lotacao, Ponto } from "../../../types/transit"
import geo from "./geo.generated.json"

/**
 * Dados simulados com geografia real de Santa Inês (MA).
 * Pontos e traçados vêm de geo.generated.json, gerado por scripts/generate-mock-geo.mjs
 * a partir do OpenStreetMap: os pontos ficam sobre a rua e os traçados seguem as vias.
 */

type GeoLinha = { pontoIds: string[]; pontoFracoes: number[]; comprimentoM: number; tracado: Coordenada[] }

export const pontos: Ponto[] = geo.pontos

/** Traçado de cada linha e a fração do percurso onde fica cada ponto. */
// JSON não tem tuplas: a forma [lat, lng] é garantida pelo script gerador.
export const geoLinhas = geo.linhas as unknown as Record<string, GeoLinha>

const metadadosLinhas: Omit<Linha, "pontoIds">[] = [
  { id: "l101", numero: "101", nome: "Centro • Rodoviária", cor: "#eab308", operacao: "05:30 às 22:40", intervalo: "A cada 18 min" },
  { id: "l203", numero: "203", nome: "Aeroporto • Centro", cor: "#2563eb", operacao: "05:10 às 23:00", intervalo: "A cada 15 min" },
  { id: "l305", numero: "305", nome: "IFMA • Hospital Macrorregional", cor: "#16a34a", operacao: "06:00 às 22:10", intervalo: "A cada 22 min" },
  { id: "l407", numero: "407", nome: "Faculdades • Estádio", cor: "#dc2626", operacao: "05:45 às 21:50", intervalo: "A cada 25 min" },
  { id: "l510", numero: "510", nome: "Circular Universitário", cor: "#7c3aed", operacao: "06:15 às 23:20", intervalo: "A cada 20 min" },
]

export const linhas: Linha[] = metadadosLinhas.map((linha) => ({ ...linha, pontoIds: geoLinhas[linha.id].pontoIds }))

/** Dados fixos de cada ônibus. A posição é calculada a partir de `progressoInicial`. */
export type OnibusSimulado = {
  id: string
  prefixo: string
  linhaId: string
  progressoInicial: number
  sentido: string
  lotacao: Lotacao
}

/** Frota simulada: um ônibus ativo por linha (5 no total), cada um num trecho diferente do percurso. */
export const onibusSimulados: OnibusSimulado[] = linhas.map((linha, linhaIndex) => ({
  id: `${linha.id}-b1`,
  prefixo: `${linha.numero}-21`,
  linhaId: linha.id,
  progressoInicial: [0.08, 0.35, 0.6, 0.22, 0.8][linhaIndex] ?? 0,
  sentido: linha.nome.split(" • ")[1] ?? "Centro",
  lotacao: (["livre", "moderado", "cheio"] as const)[linhaIndex % 3],
}))

export const avisos: Aviso[] = [
  {
    id: "a1",
    tipo: "desvio",
    titulo: "Desvio na Avenida Castelo Branco",
    descricao: "As linhas 101 e 407 circulam pela Rua do Sol entre 14h e 18h por causa de obras.",
    linhas: ["101", "407"],
    horario: "Hoje, 10:20",
  },
  {
    id: "a2",
    tipo: "atraso",
    titulo: "Trânsito intenso no Centro",
    descricao: "Chegadas podem atrasar até 8 minutos nas linhas que passam pela Praça da Matriz.",
    linhas: ["101", "203", "510"],
    horario: "Hoje, 09:45",
  },
  {
    id: "a3",
    tipo: "informacao",
    titulo: "Operação normal no fim de semana",
    descricao: "Neste sábado, todas as linhas operam nos horários habituais.",
    linhas: [],
    horario: "Ontem, 17:30",
  },
]
