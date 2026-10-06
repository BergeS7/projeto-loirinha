/**
 * Gera os ícones PNG do app (PWA e iPhone) a partir de public/icons/logo.svg e logo-maskable.svg.
 *
 * Para trocar a logo:
 *   1. Substitua public/icons/logo.svg (cantos arredondados) e public/icons/logo-maskable.svg
 *      (fundo cheio, símbolo dentro dos 66% centrais, para o Android poder recortar).
 *   2. Rode: pnpm icons
 */
import { readFile, writeFile } from "node:fs/promises"
import { Resvg } from "@resvg/resvg-js"

const dir = new URL("../public/icons/", import.meta.url)
const logo = await readFile(new URL("logo.svg", dir), "utf8")
const maskable = await readFile(new URL("logo-maskable.svg", dir), "utf8")

const icons = [
  { svg: logo, size: 192, file: "icon-192.png" },
  { svg: logo, size: 512, file: "icon-512.png" },
  { svg: maskable, size: 512, file: "icon-maskable-512.png" },
  // iPhone arredonda os cantos sozinho: usa a versão de fundo cheio.
  { svg: maskable, size: 180, file: "icon-180.png" },
]

for (const { svg, size, file } of icons) {
  const png = new Resvg(svg, { fitTo: { mode: "width", value: size } }).render().asPng()
  await writeFile(new URL(file, dir), png)
  console.log(`${file} (${size}px)`)
}
