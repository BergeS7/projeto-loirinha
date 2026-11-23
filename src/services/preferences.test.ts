/** Preferências corrompidas não podem derrubar a aplicação. */
import { beforeEach, expect, it, vi } from "vitest"
import { getBuscasRecentes, getFavoritos, alternarFavorito } from "./preferences"
import { STORAGE_KEYS } from "../config/constants"
beforeEach(() => {
  // Storage isolado evita o global experimental do Node 26 e qualquer dado do usuário.
  const entries = new Map<string, string>()
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => entries.get(key) ?? null,
    setItem: (key: string, value: string) => entries.set(key, value),
    removeItem: (key: string) => entries.delete(key),
    clear: () => entries.clear(),
  })
  localStorage.clear()
})
it("aceita somente IDs válidos sem duplicatas", () => {
  localStorage.setItem(STORAGE_KEYS.favoritos, JSON.stringify({ linhas: ["a", "a", 12, null], pontos: "inválido" }))
  expect(getFavoritos()).toEqual({ linhas: ["a"], pontos: [] })
  expect(alternarFavorito("linhas", "a").linhas).toEqual([])
})
it("trata JSON nulo e inválido como preferências vazias", () => {
  for (const value of ["null", "{", "12", "[]"]) {
    localStorage.setItem(STORAGE_KEYS.favoritos, value)
    expect(getFavoritos()).toEqual({ linhas: [], pontos: [] })
  }
})
it("filtra buscas recentes inválidas", () => {
  localStorage.setItem(STORAGE_KEYS.buscasRecentes, '[null, 12, "Centro", "", "Centro"]')
  expect(getBuscasRecentes()).toEqual(["Centro"])
})
