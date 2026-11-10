r"""Monitor de heartbeat da telemetria (processo LOCAL, emulador).

Varre /telemetry a cada --interval segundos (padrão 5) e marca como
`is_online=false` / `connection_status="connection_lost"` todo veículo cuja
última atualização válida tem mais de 45 s. Funciona sem nenhum app cliente.

Também avisa quando a viagem de um ônibus é ENCERRADA: o `end` (com ou sem
token) apaga /telemetry/{bus_id}; o monitor compara a lista de ônibus com a da
varredura anterior e imprime "viagem encerrada: <bus_id>" para cada nó que sumiu.
(Detecção por comparação: vale também para remoção manual no Emulator UI, e um
nó criado e removido dentro do mesmo intervalo entre varreduras não é visto.)

Uso (outro terminal, com os emuladores já ligados):
    .\functions\venv\Scripts\python.exe scripts\telemetry_monitor.py
    ... --once          # uma varredura e sai (código 1 se houve erro)
    ... --interval 2    # varredura mais frequente
Encerrar: Ctrl+C.

Só fala com emuladores locais e projetos "demo-*" (veja emulator_rtdb.py).
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emulator_rtdb  # noqa: E402  (também põe functions/ no sys.path)
import telemetry  # noqa: E402


def _stamp() -> str:
    return time.strftime("%H:%M:%S")


def _snapshot_ids(root):
    """Conjunto de bus_ids com nó em /telemetry agora (None se a leitura falhar)."""
    try:
        data = root.get()
    except Exception as exc:  # emulador reiniciando etc.: tenta de novo na próxima
        print(f"[{_stamp()}] ERRO ao listar /telemetry: {exc!r}", file=sys.stderr, flush=True)
        return None
    if isinstance(data, dict):
        return set(data)
    if isinstance(data, list):  # chaves numéricas viram lista no RTDB
        return {str(i) for i, v in enumerate(data) if v is not None}
    return set()


class _Reporter:
    """Imprime o resultado de cada varredura e detecta viagens encerradas."""

    def __init__(self, root):
        self.root = root
        # Linha de base: ônibus que já tinham telemetria ao ligar o monitor.
        self.known = _snapshot_ids(root) or set()

    def __call__(self, res: telemetry.SweepResult) -> None:
        for bus_id in res.marked_lost:
            print(f"[{_stamp()}] connection_lost: {bus_id}", flush=True)
        for bus_id in res.removed:
            print(f"[{_stamp()}] removido (viagem encerrada): {bus_id}", flush=True)
        for bus_id, err in res.errors:
            print(f"[{_stamp()}] ERRO {bus_id}: {err}", file=sys.stderr, flush=True)

        current = _snapshot_ids(self.root)
        if current is None:
            return
        # Nó que sumiu = `end` (com ou sem token). Os removidos pelo próprio
        # monitor já foram anunciados acima.
        for bus_id in sorted(self.known - current - set(res.removed)):
            print(f"[{_stamp()}] viagem encerrada: {bus_id} (telemetria removida)", flush=True)
        self.known = current


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", default=os.environ.get("GCLOUD_PROJECT", "loirinha-1a25f"))
    ap.add_argument("--interval", type=float, default=5.0,
                    help="segundos entre varreduras (padrao 5)")
    ap.add_argument("--once", action="store_true", help="uma varredura e sai")
    args = ap.parse_args(argv)

    root = emulator_rtdb.emulator_telemetry_root(args.project)
    db = emulator_rtdb.emulator_firestore_client(args.project)
    in_service = telemetry.firestore_in_service_checker(db)
    print(f"Monitor ligado: projeto={args.project} limite={telemetry.OFFLINE_THRESHOLD_MS // 1000}s "
          f"intervalo={args.interval}s (Ctrl+C encerra)", flush=True)
    try:
        last = telemetry.run_sweeps(
            root, in_service, iterations=1 if args.once else None,
            interval_s=args.interval, on_result=_Reporter(root))
    except KeyboardInterrupt:
        print("Monitor encerrado.", flush=True)
        return 0
    return 1 if (args.once and last is not None and last.errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
