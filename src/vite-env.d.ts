/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "mock" (padrão) usa dados simulados; "api" usa o backend em VITE_API_URL. */
  readonly VITE_DATA_SOURCE?: "mock" | "api"
  /** URL base da API, ex.: https://api.loirinha.com.br/v1 ou /api */
  readonly VITE_API_URL?: string
  /** Tempo máximo de cada requisição, em milissegundos. */
  readonly VITE_API_TIMEOUT_MS?: string

  /** Firebase (backend em backend/). Veja .env.example e docs/INTEGRACAO.md. */
  readonly VITE_FIREBASE_API_KEY?: string
  readonly VITE_FIREBASE_AUTH_DOMAIN?: string
  readonly VITE_FIREBASE_PROJECT_ID?: string
  readonly VITE_FIREBASE_DATABASE_URL?: string
  readonly VITE_FIREBASE_APP_ID?: string
  /** Região das Cloud Functions. Precisa ser "southamerica-east1". */
  readonly VITE_FUNCTIONS_REGION?: string
  /** "true" liga o SDK aos emuladores locais (Auth, Firestore, RTDB e Functions). */
  readonly VITE_USE_EMULATORS?: string
  readonly VITE_EMULATOR_HOST?: string
  readonly VITE_AUTH_PORT?: string
  readonly VITE_FIRESTORE_PORT?: string
  readonly VITE_DATABASE_PORT?: string
  readonly VITE_FUNCTIONS_PORT?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
