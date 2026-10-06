import { env } from "../../config/env"
import { apiTransitService } from "./apiTransitService"
import { mockTransitService } from "./mock/mockTransitService"
import type { TransitService } from "./TransitService"

/** Fonte de dados ativa, escolhida por VITE_DATA_SOURCE (veja .env.example). */
export const transitService: TransitService = env.dataSource === "api" ? apiTransitService : mockTransitService

export type { CallOptions, TransitService } from "./TransitService"
