/**
 * Cliente HTTP do app: toda chamada ao backend passa por aqui, com timeout, cancelamento, JSON e
 * erros padronizados.
 */
import { env } from "../config/env"

/**
 * O servidor respondeu com erro (status 4xx ou 5xx). `body` traz o corpo da resposta, quando
 * houver.
 */
export class HttpError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, message: string, body?: unknown) {
    super(message)
    this.name = "HttpError"
    this.status = status
    this.body = body
  }
}

/**
 * Não houve resposta do servidor: sem internet, servidor fora do ar, CORS bloqueado ou tempo
 * esgotado.
 */
export class NetworkError extends Error {
  constructor(message = "Não foi possível conectar ao servidor.", options?: { cause?: unknown }) {
    super(message, options)
    this.name = "NetworkError"
  }
}

type QueryValue = string | number | boolean | null | undefined

/** Opções de uma requisição. Os valores de `query` viram parâmetros da URL (vazios são ignorados). */
export type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  query?: Record<string, QueryValue>
  body?: unknown
  headers?: Record<string, string>
  signal?: AbortSignal
  timeoutMs?: number
}

function buildUrl(path: string, query?: RequestOptions["query"]) {
  const base = env.apiUrl.startsWith("http") ? env.apiUrl : `${window.location.origin}${env.apiUrl}`
  const url = new URL(`${base}/${path.replace(/^\/+/, "")}`)
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null) url.searchParams.set(key, String(value))
  }
  return url
}

/** Junta o sinal de cancelamento de quem chamou com o de timeout. */
function withTimeout(signal: AbortSignal | undefined, timeoutMs: number) {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(new DOMException("Tempo esgotado", "TimeoutError")), timeoutMs)
  const forwardAbort = () => controller.abort(signal?.reason)
  if (signal?.aborted) forwardAbort()
  signal?.addEventListener("abort", forwardAbort, { once: true })

  return {
    signal: controller.signal,
    cleanup: () => {
      window.clearTimeout(timer)
      signal?.removeEventListener("abort", forwardAbort)
    },
  }
}

async function parseBody(response: Response) {
  if (response.status === 204) return undefined
  const type = response.headers.get("content-type") ?? ""
  return type.includes("application/json") ? response.json() : response.text()
}

/**
 * Faz uma requisição à API (VITE_API_URL) e devolve o corpo da resposta. Lança HttpError para
 * status de erro e NetworkError quando o servidor não responde. Um cancelamento pedido por `signal`
 * é repassado como está.
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", query, body, headers, signal, timeoutMs = env.requestTimeoutMs } = options
  const timeout = withTimeout(signal, timeoutMs)

  try {
    const response = await fetch(buildUrl(path, query), {
      method,
      signal: timeout.signal,
      headers: {
        Accept: "application/json",
        ...(body !== undefined && { "Content-Type": "application/json" }),
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
    const data = await parseBody(response)
    if (!response.ok) throw new HttpError(response.status, `Erro ${response.status} em ${method} ${path}`, data)
    return data as T
  } catch (error) {
    if (error instanceof HttpError) throw error
    // Cancelamento pedido por quem chamou não é erro de rede: repassa como está.
    if (signal?.aborted) throw error
    throw new NetworkError(undefined, { cause: error })
  } finally {
    timeout.cleanup()
  }
}

/** Atalhos para os métodos HTTP mais usados. */
export const http = {
  get: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) => request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "POST", body }),
}
