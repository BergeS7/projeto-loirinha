/** [latitude, longitude] */
export type Coordenada = [number, number]

export type Ponto = {
  id: string
  nome: string
  referencia: string
  lat: number
  lng: number
}

export type Linha = {
  id: string
  numero: string
  nome: string
  cor: string
  pontoIds: string[]
  operacao: string
  intervalo: string
}

/** Versão reduzida da linha, usada em listas e selos. */
export type LinhaResumo = Pick<Linha, "id" | "numero" | "cor">

export type PontoProximo = Ponto & {
  distanciaKm: number
  linhas: LinhaResumo[]
}

export type Lotacao = "livre" | "moderado" | "cheio"

export type Onibus = {
  id: string
  prefixo: string
  linhaId: string
  lat: number
  lng: number
  /**
   * Distância percorrida no traçado da linha, como fração do comprimento total
   * (0 = início, 1 = fim). O mapa usa este valor para manter o ônibus sobre a rua.
   */
  progresso: number
  sentido: string
  lotacao: Lotacao
  proximoPontoId: string | null
  minutosProximoPonto: number | null
}

export type Previsao = {
  onibusId: string
  prefixo: string
  linha: Linha
  minutos: number
  lotacao: Lotacao
}

export type TipoAviso = "atraso" | "desvio" | "informacao"

export type Aviso = {
  id: string
  tipo: TipoAviso
  titulo: string
  descricao: string
  linhas: string[]
  horario: string
}

export type ResultadoBusca = {
  linhas: Linha[]
  pontos: Ponto[]
}
