/** [latitude, longitude] */
export type Coordenada = [number, number]

/** Ponto de ônibus (parada). `lat`/`lng` ficam sobre a via, onde o ônibus para. */
export type Ponto = {
  id: string
  nome: string
  referencia: string
  lat: number
  lng: number
}

/** Linha de ônibus. `pontoIds` lista as paradas na ordem do percurso. */
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

/** Ponto com a distância até o usuário e as linhas que passam por ele. */
export type PontoProximo = Ponto & {
  distanciaKm: number
  linhas: LinhaResumo[]
}

/** Nível de lotação informado para o ônibus. */
export type Lotacao = "livre" | "moderado" | "cheio"

/** Ônibus em operação: posição atual, sentido, lotação e previsão até o próximo ponto. */
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

/** Previsão de chegada de um ônibus a um ponto. */
export type Previsao = {
  onibusId: string
  prefixo: string
  linha: Linha
  minutos: number
  lotacao: Lotacao
}

/** Categoria do aviso. Define o ícone e a cor na tela. */
export type TipoAviso = "atraso" | "desvio" | "informacao"

/** Aviso de mudança na operação. */
export type Aviso = {
  id: string
  tipo: TipoAviso
  titulo: string
  descricao: string
  linhas: string[]
  horario: string
}

/** Resultado da busca por texto. */
export type ResultadoBusca = {
  linhas: Linha[]
  pontos: Ponto[]
}
