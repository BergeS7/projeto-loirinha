/**
 * Acesso ao backend Firebase (pasta backend/): login, callables, telemetria em tempo real e erros.
 *
 * Ainda não é usado pelas telas, que leem `services/transit`. O plano de ligação entre os dois
 * está em docs/INTEGRACAO.md.
 */
export * from "./auth"
export * from "./errors"
export * from "./functions"
export * from "./telemetry"
