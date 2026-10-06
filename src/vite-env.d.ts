/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "mock" (padrão) usa dados simulados; "api" usa o backend em VITE_API_URL. */
  readonly VITE_DATA_SOURCE?: "mock" | "api"
  /** URL base da API, ex.: https://api.loirinha.com.br/v1 ou /api */
  readonly VITE_API_URL?: string
  /** Tempo máximo de cada requisição, em milissegundos. */
  readonly VITE_API_TIMEOUT_MS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
