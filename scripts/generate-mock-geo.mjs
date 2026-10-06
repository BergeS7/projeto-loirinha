/**
 * Gera os dados geográficos simulados (pontos e traçados) a partir de dados reais do OpenStreetMap.
 *
 * 1. Cada ponto parte da coordenada de um lugar real de Santa Inês (via Nominatim/OSM)
 *    e é encaixado na via mais próxima por onde passam veículos (OSRM /nearest).
 * 2. O traçado de cada linha é calculado pelas ruas, passando pelos pontos na ordem (OSRM /route).
 * 3. Para cada ponto, guarda a fração do percurso onde ele fica (0 = início, 1 = fim).
 *
 * Uso: node scripts/generate-mock-geo.mjs
 * Saída: src/services/transit/mock/geo.generated.json
 *
 * Só serve para os dados simulados. Com o backend real, pontos e traçados vêm da API.
 */
import { writeFile } from "node:fs/promises"

const OSRM = "https://router.project-osrm.org"
const OUTPUT = new URL("../src/services/transit/mock/geo.generated.json", import.meta.url)

/**
 * Coordenadas de referência: lugares reais no OSM. `via` é a rua onde fica a parada:
 * o script encaixa o ponto no trecho mais próximo dessa rua (e não em estacionamentos ou vias internas).
 */
const PONTOS = [
  { id: "p1", nome: "Praça da Matriz", referencia: "Rua do Bambu, em frente à Igreja Matriz", via: "Rua do Bambú", lat: -3.65693, lng: -45.37704 },
  { id: "p2", nome: "Mercado Municipal", referencia: "Rua do Carmo", via: "Rua do Carmo", lat: -3.66332, lng: -45.37997 },
  { id: "p3", nome: "Hospital Municipal", referencia: "Av. Castelo Branco", via: "Castelo Branco", lat: -3.66512, lng: -45.38444 },
  { id: "p4", nome: "Rodoviária", referencia: "Av. Castelo Branco", via: "Castelo Branco", lat: -3.66411, lng: -45.39015 },
  { id: "p5", nome: "Estádio Municipal", referencia: "Rua Sabiá", via: "Rua Sabiá", lat: -3.66175, lng: -45.36615 },
  { id: "p6", nome: "IFMA", referencia: "Av. Castelo Branco", via: "Castelo Branco", lat: -3.65897, lng: -45.39782 },
  { id: "p7", nome: "UEMA", referencia: "Rua Porto Alegre", via: "Rua Porto Alegre", lat: -3.67361, lng: -45.38364 },
  { id: "p8", nome: "Escola Benedito Sabbak", referencia: "Rua Henrique Dias", via: "Rua Henrique Dias", lat: -3.66753, lng: -45.38818 },
  { id: "p9", nome: "Hospital Macrorregional", referencia: "Av. do Contorno", via: "Contorno", lat: -3.67631, lng: -45.3789 },
  { id: "p10", nome: "Faculdade Santa Luzia", referencia: "BR-316", lat: -3.68143, lng: -45.35146 },
  { id: "p11", nome: "Aeroporto", referencia: "Av. Brasil", via: "Avenida Brasil", lat: -3.65428, lng: -45.3452 },
  { id: "p12", nome: "Fórum", referencia: "Av. do Bambu", via: "Avenida do Bambú", lat: -3.65975, lng: -45.37098 },
  { id: "p13", nome: "Mix Mateus", referencia: "Av. Castelo Branco", via: "Castelo Branco", lat: -3.6604, lng: -45.39545 },
  { id: "p14", nome: "Cemitério São Benedito", referencia: "Rodovia Dep. João Silva", via: "João Silva", lat: -3.6445, lng: -45.37764 },
  { id: "p15", nome: "Assembleia de Deus", referencia: "Av. Luís Barros Elouf", via: "Luís Barros Elouf", lat: -3.64681, lng: -45.36864 },
  { id: "p16", nome: "Banco do Brasil", referencia: "Rua do Comércio", via: "Rua do Comércio", lat: -3.66112, lng: -45.38046 },
]

/** Distância máxima entre o lugar de referência e a parada na rua indicada. */
const MAX_DISTANCIA_VIA_M = 250

/** Ordem dos pontos em cada linha. Linhas circulares repetem o primeiro ponto no fim. */
const LINHAS = {
  l101: ["p1", "p16", "p3", "p4", "p6", "p13", "p8", "p2", "p1"],
  l203: ["p11", "p15", "p14", "p1", "p2", "p16"],
  l305: ["p6", "p13", "p4", "p8", "p7", "p9"],
  l407: ["p10", "p9", "p7", "p3", "p16", "p1", "p12", "p5"],
  l510: ["p1", "p6", "p7", "p10", "p5", "p12", "p1"],
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const round = (value) => Math.round(value * 1e6) / 1e6

async function osrm(path) {
  // Servidor público de demonstração: uma requisição por segundo.
  await sleep(1000)
  const response = await fetch(`${OSRM}${path}`, { headers: { "User-Agent": "ProjetoLoirinha/0.1 (dev script)" } })
  const data = await response.json()
  if (data.code !== "Ok") throw new Error(`OSRM ${path}: ${data.code} ${data.message ?? ""}`)
  return data
}

function metros(a, b) {
  const R = 6371000
  const toRad = (deg) => (deg * Math.PI) / 180
  const dLat = toRad(b[0] - a[0])
  const dLng = toRad(b[1] - a[1])
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a[0])) * Math.cos(toRad(b[0])) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

const normalizar = (texto) => texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()

const pontos = []
for (const { via, ...ponto } of PONTOS) {
  const { waypoints } = await osrm(`/nearest/v1/driving/${ponto.lng},${ponto.lat}?number=40`)
  const naVia = via && waypoints.find((w) => normalizar(w.name).includes(normalizar(via)) && w.distance <= MAX_DISTANCIA_VIA_M)
  const escolhido = naVia || waypoints[0]
  if (via && !naVia) console.warn(`  aviso: ${ponto.id} não achou "${via}" por perto; usando a via mais próxima`)
  const [lng, lat] = escolhido.location
  console.log(`${ponto.id} ${ponto.nome}: "${escolhido.name || "via sem nome"}" a ${escolhido.distance.toFixed(0)} m da referência`)
  pontos.push({ ...ponto, lat: round(lat), lng: round(lng) })
}
const pontoPorId = new Map(pontos.map((ponto) => [ponto.id, ponto]))

const linhas = {}
for (const [linhaId, pontoIds] of Object.entries(LINHAS)) {
  const coords = pontoIds.map((id) => `${pontoPorId.get(id).lng},${pontoPorId.get(id).lat}`).join(";")
  const { routes } = await osrm(`/route/v1/driving/${coords}?overview=full&geometries=geojson&continue_straight=false`)
  const tracado = routes[0].geometry.coordinates.map(([lng, lat]) => [round(lat), round(lng)])

  const acumulado = [0]
  for (let i = 1; i < tracado.length; i++) acumulado.push(acumulado[i - 1] + metros(tracado[i - 1], tracado[i]))
  const total = acumulado.at(-1)

  // Cada ponto é um vértice do traçado (fim de um trecho). Pega a primeira passagem adiante do ponto
  // anterior, para não confundir quando a linha passa duas vezes pela mesma rua.
  let inicio = 0
  const pontoFracoes = pontoIds.map((id, ordem) => {
    const alvo = [pontoPorId.get(id).lat, pontoPorId.get(id).lng]
    const de = ordem === 0 ? 0 : inicio + 1
    let indice = tracado.findIndex((coord, i) => i >= de && metros(coord, alvo) < 3)
    if (indice === -1) {
      indice = de
      for (let i = de; i < tracado.length; i++) if (metros(tracado[i], alvo) < metros(tracado[indice], alvo)) indice = i
      console.warn(`  aviso: ${id} na linha ${linhaId} a ${metros(tracado[indice], alvo).toFixed(0)} m do traçado`)
    }
    inicio = indice
    return round(acumulado[indice] / total)
  })

  console.log(`${linhaId}: ${(total / 1000).toFixed(1)} km, ${tracado.length} vértices`)
  linhas[linhaId] = { pontoIds, pontoFracoes, comprimentoM: Math.round(total), tracado }
}

const centro = pontoPorId.get("p1")
await writeFile(
  OUTPUT,
  JSON.stringify({ fonte: "OpenStreetMap (ODbL) via OSRM", centro: [centro.lat, centro.lng], pontos, linhas }),
)
console.log(`Gerado: ${OUTPUT.pathname}`)
