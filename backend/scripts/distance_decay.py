r"""Simulador de `distance` para ônibus SEM CONEXÃO (processo LOCAL, emulador).

A cada --interval segundos (padrão 30), para cada /telemetry/{bus_id} com
`connection_status == "connection_lost"`, `distance` (km) diminui conforme a
velocidade registrada em `speed` (km/h):

    distance_nova = max(0, distance - speed * interval / 3600)

Regras:
  * Só mexe em nós `connection_lost` com `distance` e `speed` numéricos válidos,
    `speed > 0` e `distance > 0`. Caso contrário não escreve nada.
  * Quando chega telemetria nova, `sendTelemetry` regrava o nó (online, com a
    `distance` enviada pelo motorista) e este script PARA de editá-lo. A escrita
    é condicional por ETag: se a telemetria chegar entre a leitura e a escrita,
    a escrita é descartada, o nó é relido e já aparece online (nada é feito).
  * Grava só `distance` e `distance_adjusted_at` (hora do servidor, ms Unix).
    NÃO altera `updated_at`, `captured_at`, `is_online` nem `connection_status`;
    logo, não interfere no monitor de heartbeat.

ATENÇÃO: é uma SIMULAÇÃO (linha reta, velocidade constante = último `speed`,
sem trânsito, paradas ou desvios). `distance` NÃO vem de um passageiro real.

Uso (outro terminal, com os emuladores ligados):
    .\functions\venv\Scripts\python.exe scripts\distance_decay.py
    ... --once            # um ciclo e sai (código 1 se houve erro)
    ... --interval 10     # ciclo mais curto (a fórmula usa o mesmo intervalo)
Encerrar: Ctrl+C. Só fala com emuladores locais (veja emulator_rtdb.py).
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emulator_rtdb  # noqa: E402  (também põe functions/ no sys.path)
import telemetry  # noqa: E402

DEFAULT_INTERVAL_S = 30.0
MAX_CAS_RETRIES = 10
DISTANCE_DECIMALS = 3  # km -> precisão de metro


def _num(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def next_distance(node: Any, step_s: float = DEFAULT_INTERVAL_S) -> float | None:
    """Nova distância (km) para este nó, ou None se não há o que ajustar."""
    if not isinstance(node, dict):
        return None
    if node.get("connection_status") != telemetry.CONNECTION_LOST:
        return None
    distance, speed = node.get("distance"), node.get("speed")
    if not _num(distance) or distance <= 0:
        return None
    if not _num(speed) or speed <= 0:
        return None  # parado/inválido: distância não muda
    return round(max(0.0, distance - speed * step_s / 3600.0), DISTANCE_DECIMALS)


def adjust_node(root, bus_id: str, step_s: float, now_ms: int) -> str:
    """Ajusta UM nó. Devolve "adjusted" | "skipped" | "gone"."""
    ref = root.child(bus_id)
    for _ in range(MAX_CAS_RETRIES):
        cur, etag = ref.get(etag=True)
        if cur is None:
            return "gone"
        new_distance = next_distance(cur, step_s)
        if new_distance is None:
            return "skipped"  # online de novo, sem distance, parado...
        new = dict(cur)
        new["distance"] = new_distance
        new["distance_adjusted_at"] = now_ms
        ok, _, _ = ref.set_if_unchanged(etag, new)
        if ok:
            return "adjusted"
        # ETag mudou: chegou telemetria (ou o monitor mexeu). Relê e reavalia.
    raise telemetry.TelemetryError("aborted", "contention",
                                   "Muita concorrência neste veículo.")


@dataclass
class TickResult:
    now_ms: int
    adjusted: list = field(default_factory=list)  # (bus_id, distance_nova)
    errors: list = field(default_factory=list)


def _candidates(root) -> list[str]:
    data = root.get()
    if isinstance(data, list):  # chaves numéricas viram lista no RTDB
        data = {str(i): v for i, v in enumerate(data) if v is not None}
    if not isinstance(data, dict):
        return []
    return [b for b, n in data.items() if next_distance(n) is not None]


def tick(root, step_s: float = DEFAULT_INTERVAL_S,
         now_ms: int | None = None) -> TickResult:
    now_ms = telemetry.now_ms() if now_ms is None else now_ms
    result = TickResult(now_ms=now_ms)
    for bus_id in _candidates(root):
        try:
            if adjust_node(root, bus_id, step_s, now_ms) == "adjusted":
                result.adjusted.append((bus_id, root.child(bus_id).get().get("distance")))
        except Exception as exc:  # um ônibus com problema não para os demais
            result.errors.append((bus_id, repr(exc)))
    return result


def run_loop(root, *, interval_s: float = DEFAULT_INTERVAL_S,
             iterations: int | None = None,
             sleep: Callable[[float], None] = time.sleep,
             on_result: Callable[[TickResult], None] | None = None
             ) -> TickResult | None:
    last, done = None, 0
    while iterations is None or done < iterations:
        try:
            last = tick(root, interval_s)
        except Exception as exc:  # emulador reiniciando etc.: tenta no próximo ciclo
            last = TickResult(now_ms=telemetry.now_ms(), errors=[("*", repr(exc))])
        if on_result is not None:
            on_result(last)
        done += 1
        if iterations is not None and done >= iterations:
            break
        sleep(interval_s)
    return last


def _report(res: TickResult) -> None:
    stamp = time.strftime("%H:%M:%S")
    for bus_id, dist in res.adjusted:
        print(f"[{stamp}] distance ajustada: {bus_id} -> {dist} km", flush=True)
    for bus_id, err in res.errors:
        print(f"[{stamp}] ERRO {bus_id}: {err}", file=sys.stderr, flush=True)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", default=os.environ.get("GCLOUD_PROJECT", "loirinha-1a25f"))
    ap.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S,
                    help="segundos entre ciclos (padrao 30)")
    ap.add_argument("--once", action="store_true", help="um ciclo e sai")
    args = ap.parse_args(argv)
    if args.interval <= 0:
        ap.error("--interval deve ser > 0")

    root = emulator_rtdb.emulator_telemetry_root(args.project)
    print(f"Ajuste de distance ligado: projeto={args.project} "
          f"intervalo={args.interval:g}s (Ctrl+C encerra)", flush=True)
    try:
        last = run_loop(root, interval_s=args.interval,
                        iterations=1 if args.once else None, on_result=_report)
    except KeyboardInterrupt:
        print("Encerrado.", flush=True)
        return 0
    return 1 if (args.once and last is not None and last.errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
