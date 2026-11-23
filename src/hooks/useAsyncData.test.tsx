/** Regressões de polling lento, cancelamento e preservação dos dados válidos. */
import { act, cleanup, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import useAsyncData from "./useAsyncData"

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})
describe("useAsyncData", () => {
  it("permite consulta mais lenta que o intervalo sem cancelá-la", async () => {
    vi.useFakeTimers()
    let complete: (value: string) => void
    let signal = new AbortController().signal
    const loader = vi.fn((current: AbortSignal) => {
      signal = current
      return new Promise<string>((resolve) => {
        complete = resolve
      })
    })
    const { result } = renderHook(() => useAsyncData(loader, [], { refreshInterval: 3000 }))
    await act(async () => {
      vi.advanceTimersByTime(9000)
    })
    expect(loader).toHaveBeenCalledTimes(1)
    expect(signal.aborted).toBe(false)
    await act(async () => {
      complete("posição")
    })
    expect(result.current.data).toBe("posição")
    expect(result.current.updatedAt).toBeDefined()
  })
  it("preserva dados e timestamp quando a atualização falha", async () => {
    const loader = vi.fn().mockResolvedValueOnce("posição").mockRejectedValueOnce(new Error("offline"))
    const { result } = renderHook(() => useAsyncData(loader, []))
    await act(async () => {})
    const timestamp = result.current.updatedAt
    await act(async () => {
      result.current.reload()
    })
    expect(result.current.data).toBe("posição")
    expect(result.current.error).toBeInstanceOf(Error)
    expect(result.current.updatedAt).toBe(timestamp)
    expect(result.current.loading).toBe(false)
  })
  it("cancela consultas ao trocar de recurso ou desmontar", async () => {
    const signals: AbortSignal[] = []
    const loader = (signal: AbortSignal) => {
      signals.push(signal)
      return new Promise<string>(() => {})
    }
    const { rerender, unmount } = renderHook(({ id }) => useAsyncData(loader, [id]), { initialProps: { id: "a" } })
    rerender({ id: "b" })
    expect(signals[0].aborted).toBe(true)
    expect(signals[1].aborted).toBe(false)
    unmount()
    expect(signals[1].aborted).toBe(true)
  })
})
