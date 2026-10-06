# Contrato da API

Este é o contrato que o frontend espera do backend. A implementação HTTP está em
`src/services/transit/apiTransitService.ts` e os tipos em `src/types/transit.ts`.

Se o backend responder em outro formato, converta os dados em `apiTransitService.ts`.
As telas não precisam mudar.

## Convenções

- Todas as rotas são relativas a `VITE_API_URL`.
- Respostas em JSON (`Content-Type: application/json`), com campos em `camelCase`.
- Coordenadas em graus decimais (`lat`, `lng`).
- Um recurso inexistente responde **404**. O frontend mostra "não encontrado" em vez de erro.
- Outros erros (4xx/5xx) aparecem na tela como "Não foi possível carregar", com o botão "Tentar de novo".
- Rotas `GET` podem ser guardadas em cache pelo service worker para uso offline (até 24 h).

## Endpoints

| Método | Rota | Resposta | Uso |
| --- | --- | --- | --- |
| GET | `/linhas` | `Linha[]` | Favoritos, atalhos da tela inicial |
| GET | `/linhas/{id}` | `Linha` ou 404 | Detalhe da linha, acompanhamento |
| GET | `/linhas/{id}/itinerario` | `Ponto[]` na ordem do percurso | Lista de pontos da linha |
| GET | `/linhas/{id}/tracado` | `[lat, lng][]` pelas ruas, na ordem do percurso | Desenho da linha e movimento dos ônibus |
| GET | `/pontos` | `Ponto[]` | Favoritos |
| GET | `/pontos/{id}` | `Ponto` ou 404 | Detalhe do ponto |
| GET | `/pontos/proximos?lat=&lng=&limite=` | `PontoProximo[]` do mais perto ao mais longe | Tela inicial |
| GET | `/pontos/{id}/previsoes` | `Previsao[]` do mais cedo ao mais tarde | Detalhe do ponto (a cada 15 s) |
| GET | `/onibus?linhaId=` | `Onibus[]`. Sem `linhaId`, todos | Mapas (a cada 3 s) |
| GET | `/avisos` | `Aviso[]` | Tela de avisos |
| GET | `/busca?q=` | `{ linhas: Linha[], pontos: Ponto[] }` | Busca |

## Tipos

```ts
type Ponto = { id: string; nome: string; referencia: string; lat: number; lng: number }

type Linha = {
  id: string
  numero: string        // "101"
  nome: string          // "Centro • Rodoviária"
  cor: string           // cor hexadecimal, ex.: "#eab308"
  pontoIds: string[]
  operacao: string      // "05:30 às 22:40"
  intervalo: string     // "A cada 18 min"
}

type PontoProximo = Ponto & {
  distanciaKm: number
  linhas: { id: string; numero: string; cor: string }[]
}

type Lotacao = "livre" | "moderado" | "cheio"

type Onibus = {
  id: string
  prefixo: string                     // "101-21"
  linhaId: string
  lat: number                         // posição do GPS (reserva, veja "Geografia")
  lng: number
  progresso: number                   // 0 a 1: fração do traçado já percorrida
  sentido: string
  lotacao: Lotacao
  proximoPontoId: string | null
  minutosProximoPonto: number | null
}

type Previsao = { onibusId: string; prefixo: string; linha: Linha; minutos: number; lotacao: Lotacao }

type Aviso = {
  id: string
  tipo: "atraso" | "desvio" | "informacao"
  titulo: string
  descricao: string
  linhas: string[]   // números das linhas afetadas
  horario: string    // texto já formatado, ex.: "Hoje, 10:20"
}
```

## Geografia: pontos, traçados e posição dos ônibus

O mapa nunca liga pontos em linha reta. Por isso o backend precisa garantir:

- **Pontos (`Ponto.lat/lng`)**: a localização real da parada, sobre a via onde o ônibus para, e não no
  centro de um prédio ou praça.
- **Traçado (`/linhas/{id}/tracado`)**: a sequência de coordenadas `[lat, lng]` do percurso **pelas ruas**,
  passando pelos pontos na ordem do itinerário. Use pontos suficientes para acompanhar as curvas
  (por exemplo, a geometria de um roteador como OSRM ou Valhalla, ou o traçado registrado pelo GPS).
- **Ônibus (`Onibus.progresso`)**: a distância já percorrida no traçado, como fração do comprimento total
  (0 = início, 1 = fim). O mapa posiciona o ônibus com este valor sobre o traçado, então ele fica
  sempre na rua, mesmo que o GPS tenha erro de alguns metros. O backend deve calcular o `progresso`
  projetando a posição do GPS no traçado (map matching). `lat/lng` só são usados enquanto o traçado
  não carregou, e nesse caso o ônibus é reposicionado sem animação.
- `proximoPontoId` e `minutosProximoPonto` devem considerar a distância pelo traçado, não em linha reta.

Os dados simulados seguem as mesmas regras: são gerados por `scripts/generate-mock-geo.mjs` com dados
do OpenStreetMap (veja o próprio script).

## Tempo real

As posições dos ônibus são consultadas por polling (`GET /onibus` a cada 3 s, em
`src/hooks/transit.ts`). Para trocar por WebSocket ou SSE depois, altere só o
`useBusPositions`. As telas não mudam.
