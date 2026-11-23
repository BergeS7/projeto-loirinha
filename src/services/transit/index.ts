/**
 * Ponto único de acesso aos dados: escolhe a implementação simulada ou REST
 * conforme VITE_DATA_SOURCE.
 */

import { env } from "../../config/env"

import type { TransitService } from "./TransitService"

/** Fonte de dados ativa, escolhida por VITE_DATA_SOURCE (veja .env.example). */

let service: Promise<TransitService> | undefined

/** Importa uma vez, sob demanda: modo mock não baixa o SDK Firebase. */

function load(): Promise<TransitService> {
  service ??=
    env.dataSource === "api"
      ? import("./apiTransitService").then((module) => module.apiTransitService)
      : import("./mock/mockTransitService").then((module) => module.mockTransitService)

  return service
}

/** Fachada estável preserva o contrato das páginas com carregamento assíncrono. */

export const transitService: TransitService = {
  getLinhas: async (options) => (await load()).getLinhas(options),

  getLinha: async (id, options) => (await load()).getLinha(id, options),

  getItinerario: async (id, options) => (await load()).getItinerario(id, options),

  getTracado: async (id, options) => (await load()).getTracado(id, options),

  getPontos: async (options) => (await load()).getPontos(options),

  getPonto: async (id, options) => (await load()).getPonto(id, options),

  getPontosProximos: async (position, limit, options) => (await load()).getPontosProximos(position, limit, options),

  getPrevisoes: async (id, options) => (await load()).getPrevisoes(id, options),

  getOnibus: async (id, options) => (await load()).getOnibus(id, options),

  getAvisos: async (options) => (await load()).getAvisos(options),

  buscar: async (query, options) => (await load()).buscar(query, options),
}

export type { CallOptions, TransitService } from "./TransitService"
