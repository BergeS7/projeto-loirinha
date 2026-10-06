export type DataSource = "mock" | "api"

const apiUrl = (import.meta.env.VITE_API_URL ?? "").trim().replace(/\/+$/, "")
const requestedSource: DataSource = import.meta.env.VITE_DATA_SOURCE === "api" ? "api" : "mock"

if (requestedSource === "api" && !apiUrl) {
  console.warn("[config] VITE_DATA_SOURCE=api, mas VITE_API_URL não foi definida. Usando dados simulados.")
}

export const env = {
  dataSource: (requestedSource === "api" && apiUrl ? "api" : "mock") as DataSource,
  apiUrl,
  requestTimeoutMs: Number(import.meta.env.VITE_API_TIMEOUT_MS) || 10_000,
} as const
