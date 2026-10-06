/**
 * Implementação simulada do TransitService: ônibus andando pelos traçados reais e previsões
 * calculadas pela distância nas ruas. Não depende de internet nem de backend.
 */
import { normalizarTexto } from "../../../lib/format"
import { distanciaKm } from "../../../lib/geo"
import { buildRoutePath, pointAlong } from "../../../lib/route"
import type { Linha, Onibus, Ponto, Previsao } from "../../../types/transit"
import type { TransitService } from "../TransitService"
import { avisos, geoLinhas, linhas, onibusSimulados, pontos } from "./mockData"

/** Velocidade média simulada dos ônibus: ~22 km/h, comum no trânsito urbano. */
const VELOCIDADE_MS = 6

/** Simula a latência de rede e respeita o cancelamento, como uma requisição real. */
function latencia(signal?: AbortSignal, ms = 220) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(signal.reason)
    const timer = window.setTimeout(resolve, ms)
    signal?.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timer)
        reject(signal.reason)
      },
      { once: true },
    )
  })
}

const pontoPorId = new Map(pontos.map((ponto) => [ponto.id, ponto]))
const linhaPorId = new Map(linhas.map((linha) => [linha.id, linha]))

function itinerario(linha: Linha): Ponto[] {
  return linha.pontoIds.map((id) => pontoPorId.get(id)).filter((ponto): ponto is Ponto => Boolean(ponto))
}

const rotaPorLinha = new Map(Object.entries(geoLinhas).map(([id, geoLinha]) => [id, buildRoutePath(geoLinha.tracado)]))

/** Quanto falta (em fração do percurso) do progresso `de` até `ate`, dando a volta no fim da linha. */
const fracaoAte = (de: number, ate: number) => (ate - de + 1) % 1

const minutosPorFracao = (fracao: number, comprimentoM: number) =>
  Math.max(1, Math.round((fracao * comprimentoM) / VELOCIDADE_MS / 60))

/** Cada ônibus anda sobre o traçado da linha (pelas ruas), a partir da distância percorrida. */
function onibusEmMovimento(linhaId?: string): Onibus[] {
  const segundos = Date.now() / 1000

  return onibusSimulados
    .filter((bus) => !linhaId || bus.linhaId === linhaId)
    .map(({ progressoInicial, ...bus }) => {
      const rota = rotaPorLinha.get(bus.linhaId)!
      const { pontoIds, pontoFracoes } = geoLinhas[bus.linhaId]
      const progresso = (progressoInicial + (segundos * VELOCIDADE_MS) / rota.total) % 1
      const [lat, lng] = pointAlong(rota, progresso).position
      const proximo = Math.max(0, pontoFracoes.findIndex((fracao) => fracao > progresso))

      return {
        ...bus,
        progresso,
        lat,
        lng,
        proximoPontoId: pontoIds[proximo] ?? null,
        minutosProximoPonto: minutosPorFracao(fracaoAte(progresso, pontoFracoes[proximo]), rota.total),
      }
    })
}

/**
 * Fonte de dados simulada, usada quando VITE_DATA_SOURCE não é "api". Responde com uma pequena
 * espera artificial, para imitar a rede.
 */
export const mockTransitService: TransitService = {
  async getLinhas({ signal } = {}) {
    await latencia(signal)
    return linhas
  },

  async getLinha(id, { signal } = {}) {
    await latencia(signal, 180)
    return linhaPorId.get(id) ?? null
  },

  async getItinerario(linhaId, { signal } = {}) {
    await latencia(signal, 180)
    const linha = linhaPorId.get(linhaId)
    return linha ? itinerario(linha) : []
  },

  async getPontos({ signal } = {}) {
    await latencia(signal)
    return pontos
  },

  async getPonto(id, { signal } = {}) {
    await latencia(signal, 180)
    return pontoPorId.get(id) ?? null
  },

  async getPontosProximos([lat, lng], limite, { signal } = {}) {
    await latencia(signal)
    return pontos
      .map((ponto) => ({
        ...ponto,
        distanciaKm: distanciaKm({ lat, lng }, ponto),
        linhas: linhas
          .filter((linha) => linha.pontoIds.includes(ponto.id))
          .map(({ id, numero, cor }) => ({ id, numero, cor })),
      }))
      .sort((a, b) => a.distanciaKm - b.distanciaKm)
      .slice(0, limite)
  },

  async getTracado(linhaId, { signal } = {}) {
    await latencia(signal, 120)
    return geoLinhas[linhaId]?.tracado ?? []
  },

  async getPrevisoes(pontoId, { signal } = {}) {
    await latencia(signal, 200)
    if (!pontoPorId.has(pontoId)) return []

    return onibusEmMovimento()
      .map((bus): Previsao | null => {
        const { pontoIds, pontoFracoes } = geoLinhas[bus.linhaId]
        // Linhas circulares passam pelo mesmo ponto mais de uma vez: vale a passagem mais próxima.
        const fracoes = pontoFracoes.filter((_, i) => pontoIds[i] === pontoId)
        if (fracoes.length === 0) return null
        const falta = Math.min(...fracoes.map((fracao) => fracaoAte(bus.progresso, fracao)))
        const minutos = minutosPorFracao(falta, rotaPorLinha.get(bus.linhaId)!.total)
        return { onibusId: bus.id, prefixo: bus.prefixo, linha: linhaPorId.get(bus.linhaId)!, minutos, lotacao: bus.lotacao }
      })
      .filter((item): item is Previsao => item !== null)
      .sort((a, b) => a.minutos - b.minutos)
  },

  async getOnibus(linhaId, { signal } = {}) {
    await latencia(signal, 80)
    return onibusEmMovimento(linhaId)
  },

  async getAvisos({ signal } = {}) {
    await latencia(signal)
    return avisos
  },

  async buscar(termo, { signal } = {}) {
    await latencia(signal, 180)
    const busca = normalizarTexto(termo)
    if (!busca) return { linhas: [], pontos: [] }
    return {
      linhas: linhas.filter((linha) => normalizarTexto(`${linha.numero} ${linha.nome}`).includes(busca)),
      pontos: pontos.filter((ponto) => normalizarTexto(`${ponto.nome} ${ponto.referencia}`).includes(busca)),
    }
  },
}
