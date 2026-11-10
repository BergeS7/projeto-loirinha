r"""Seed da colecao `routes` no Firestore EMULATOR (nunca em producao).

Uso (PowerShell, na raiz do projeto, com o Firestore Emulator rodando):

  functions\venv\Scripts\python.exe scripts\seed_routes.py
  functions\venv\Scripts\python.exe scripts\seed_routes.py --dry-run
  functions\venv\Scripts\python.exe scripts\seed_routes.py --skip-existing
  functions\venv\Scripts\python.exe scripts\seed_routes.py --only route002

O que a gravacao faz
  Para cada rota usa `set()` no documento routes/<id>:
    - se o documento NAO existe, ele e criado;
    - se JA existe, ele e SUBSTITUIDO inteiro pelo conteudo definido aqui
      (campos adicionados a mao nesse documento sao perdidos).
  Com --skip-existing so cria documentos novos e nunca sobrescreve.
  O script nunca apaga a colecao nem mexe em outros documentos.

Seguranca
  So conecta em host local (127.0.0.1/localhost) definido por
  FIRESTORE_EMULATOR_HOST (padrao 127.0.0.1:8080) e em projeto "demo-*" ou "loirinha-1a25f".

Codigos de saida: 0 ok | 1 dados invalidos/uso | 2 ambiente/emulador | 3 erro de gravacao
"""
from __future__ import annotations

import argparse
import copy
import math
import os
import re
import socket
import sys
from typing import Any, Callable

PROJECT_ID = os.environ.get("GCLOUD_PROJECT", "loirinha-1a25f")
DEFAULT_EMULATOR_HOST = "127.0.0.1:8080"
COLLECTION = "routes"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
IO_TIMEOUT = 15.0  # segundos por operacao no Firestore

# --------------------------------------------------------------------------
# DADOS. Para adicionar uma rota, inclua uma nova chave neste dicionario.
# A chave e o ID do documento (routes/<id>); ela NAO e gravada como campo.
# --------------------------------------------------------------------------
ROUTES: dict[str, dict[str, Any]] = {
    # Dados de exemplo fornecidos pelo projeto (valores ficticios).
    "route001": {
        "name": "Centro - Rodoviária",
        "origin": {"name": "Terminal Central",
                   "latitude": -3.668, "longitude": -45.381},
        "destination": {"name": "Terminal Rodoviário",
                        "latitude": -3.674, "longitude": -45.389},
        "stops": [
            {"name": "Praça Central", "latitude": -3.669,
             "longitude": -45.383, "order": 1},
            {"name": "Hospital", "latitude": -3.671,
             "longitude": -45.385, "order": 2},
        ],
        # Cores da linha no mapa: frias = rota prevista; quentes = desvio.
        "color_hex_route": "#1E88E5",      # azul
        "color_hex_out_route": "#FF6D00",  # laranja
    },
    # Santa Ines -> Pindare-Mirim (MA).
    # ATENCAO: as coordenadas sao APROXIMADAS e se referem a localizacao dos
    # municipios (sede), nao a terminais de onibus nem ao percurso da estrada.
    #   Santa Ines: -3.6667, -45.3800 (Wikipedia pt: 3o40'00"S 45o22'48"O;
    #               cidade-brasil.com.br: -3.66694, -45.38)
    #   Pindare-Mirim: -3.6078, -45.3428 (cidade-brasil.com.br: -3.60778,
    #               -45.3428; fonte unica, secundaria)
    # `stops` fica vazio de proposito: nao ha evidencia de pontos de parada
    # oficiais desta linha. Inclua paradas aqui apenas quando forem conhecidas.
    "route002": {
        "name": "Santa Inês - Pindaré-Mirim",
        "origin": {"name": "Santa Inês",
                   "latitude": -3.6667, "longitude": -45.38},
        "destination": {"name": "Pindaré-Mirim",
                        "latitude": -3.6078, "longitude": -45.3428},
        "stops": [],
        "color_hex_route": "#00897B",      # verde-azulado (teal)
        "color_hex_out_route": "#E53935",  # vermelho
    },
}


class SeedError(Exception):
    """Erro esperado, com mensagem pronta para o usuario e codigo de saida."""

    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


# ------------------------------------------------------------ validacao ----
_PLACE_KEYS = {"name", "latitude", "longitude"}
_STOP_KEYS = _PLACE_KEYS | {"order"}
_COLOR_KEYS = ("color_hex_route", "color_hex_out_route")
_ROUTE_KEYS = {"name", "origin", "destination", "stops", *_COLOR_KEYS}
_HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{6}")


def _is_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _check_text(path: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: deve ser texto não vazio (recebido {value!r})")


def _check_coord(path: str, value: Any, limit: float, errors: list[str]) -> None:
    if not _is_number(value):
        errors.append(f"{path}: deve ser número (recebido {value!r})")
    elif not -limit <= value <= limit:
        errors.append(f"{path}: deve estar entre -{limit:g} e {limit:g} "
                      f"(recebido {value})")


def _check_place(path: str, place: Any, allowed: set[str],
                 errors: list[str]) -> None:
    if not isinstance(place, dict):
        errors.append(f"{path}: deve ser um objeto (recebido {place!r})")
        return
    for key in sorted(allowed - set(place)):
        errors.append(f"{path}.{key}: ausente")
    for key in sorted(set(place) - allowed):
        errors.append(f"{path}.{key}: campo inesperado")
    if "name" in place:
        _check_text(f"{path}.name", place["name"], errors)
    if "latitude" in place:
        _check_coord(f"{path}.latitude", place["latitude"], 90, errors)
    if "longitude" in place:
        _check_coord(f"{path}.longitude", place["longitude"], 180, errors)


def _check_color(path: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or not _HEX_COLOR.fullmatch(value):
        errors.append(f"{path}: deve ser cor hexadecimal #RRGGBB "
                      f"(recebido {value!r})")


def validate_route(route_id: Any, data: Any) -> list[str]:
    """Devolve a lista de problemas (vazia = rota valida)."""
    errors: list[str] = []
    if (not isinstance(route_id, str) or not route_id.strip()
            or "/" in route_id or route_id in {".", ".."}
            or (route_id.startswith("__") and route_id.endswith("__"))):
        errors.append(f"id: ID de documento inválido ({route_id!r})")
    if not isinstance(data, dict):
        errors.append("documento: deve ser um objeto")
        return errors

    for key in sorted(_ROUTE_KEYS - set(data)):
        errors.append(f"{key}: ausente")
    for key in sorted(set(data) - _ROUTE_KEYS):
        errors.append(f"{key}: campo inesperado")

    if "name" in data:
        _check_text("name", data["name"], errors)
    if "origin" in data:
        _check_place("origin", data["origin"], _PLACE_KEYS, errors)
    if "destination" in data:
        _check_place("destination", data["destination"], _PLACE_KEYS, errors)

    for key in _COLOR_KEYS:
        if key in data:
            _check_color(key, data[key], errors)

    if "stops" in data:
        stops = data["stops"]
        if not isinstance(stops, list):
            errors.append(f"stops: deve ser uma lista (recebido {stops!r})")
        else:
            orders: list[int] = []
            for i, stop in enumerate(stops):
                path = f"stops[{i}]"
                _check_place(path, stop, _STOP_KEYS, errors)
                if isinstance(stop, dict) and "order" in stop:
                    order = stop["order"]
                    if (not isinstance(order, int) or isinstance(order, bool)
                            or order <= 0):
                        errors.append(f"{path}.order: deve ser inteiro "
                                      f"positivo (recebido {order!r})")
                    else:
                        orders.append(order)
            repeated = sorted({o for o in orders if orders.count(o) > 1})
            if repeated:
                errors.append(f"stops: ordens repetidas {repeated}")
    return errors


def validate_routes(routes: dict[str, Any]) -> dict[str, list[str]]:
    """Mapa {id: problemas} apenas das rotas inválidas."""
    result = {}
    for route_id, data in routes.items():
        problems = validate_route(route_id, data)
        if problems:
            result[route_id] = problems
    return result


# -------------------------------------------------------------- ambiente ----
def _split_host(host: str) -> tuple[str, int]:
    name, sep, port = host.strip().rpartition(":")
    if not sep or not port.isdigit():
        raise SeedError(
            f"FIRESTORE_EMULATOR_HOST inválido ({host!r}). "
            "Use o formato host:porta, por exemplo 127.0.0.1:8080.", 2)
    return name.strip("[]"), int(port)


def resolve_emulator_host(environ: dict[str, str] | None = None) -> str:
    """Host:porta do emulador; recusa qualquer host que não seja local."""
    env = os.environ if environ is None else environ
    host = (env.get("FIRESTORE_EMULATOR_HOST") or DEFAULT_EMULATOR_HOST).strip()
    name, _ = _split_host(host)
    if name not in LOOPBACK_HOSTS:
        raise SeedError(
            f"Recusado: FIRESTORE_EMULATOR_HOST={host!r} não é um host local. "
            "Este seed só grava no emulador da sua própria máquina.", 2)
    return host


def check_project_id(project_id: str) -> None:
    if not (project_id.startswith("demo-") or project_id == "loirinha-1a25f"):
        raise SeedError(
            f"Recusado: o projeto {project_id!r} não é 'demo-*' nem 'loirinha-1a25f'. "
            "Use um projeto de demonstração ou o projeto loirinha-1a25f (só emulador).", 2)


def check_emulator_reachable(host: str, timeout: float = 3.0) -> None:
    name, port = _split_host(host)
    try:
        with socket.create_connection((name, port), timeout=timeout):
            pass
    except OSError as exc:
        raise SeedError(
            f"Não consegui conectar ao Firestore Emulator em {host}. "
            "Ele está rodando? Inicie com .\\scripts\\start-emulators.ps1 "
            "e rode o seed de novo.", 2) from exc


def make_client(host: str, project_id: str):
    """Cliente Firestore apontado para o emulador (sem credenciais reais)."""
    os.environ["FIRESTORE_EMULATOR_HOST"] = host  # força o modo emulador
    try:
        from google.auth.credentials import AnonymousCredentials
        from google.cloud import firestore
    except ImportError as exc:
        raise SeedError(
            "Biblioteca google-cloud-firestore não encontrada. Rode com o "
            "Python do projeto: functions\\venv\\Scripts\\python.exe", 2) from exc
    return firestore.Client(project=project_id,
                            credentials=AnonymousCredentials())


# ------------------------------------------------------------- gravação ----
def seed_routes(db, routes: dict[str, Any], skip_existing: bool = False,
                log: Callable[[str], None] = print) -> list[tuple[str, str]]:
    """Grava as rotas. Valida TODAS antes de gravar qualquer uma.

    Devolve [(id, "created" | "updated" | "skipped"), ...].
    """
    problems = validate_routes(routes)
    if problems:
        lines = [f"  - {rid}: {p}" for rid, ps in problems.items() for p in ps]
        raise SeedError("Dados inválidos; nada foi gravado:\n" + "\n".join(lines), 1)

    from google.api_core import exceptions as gexc

    results: list[tuple[str, str]] = []
    for route_id, data in routes.items():
        ref = db.collection(COLLECTION).document(route_id)
        path = f"{COLLECTION}/{route_id}"
        try:
            exists = ref.get(timeout=IO_TIMEOUT).exists
            if skip_existing and exists:
                status = "skipped"
            elif skip_existing:
                ref.create(copy.deepcopy(data), timeout=IO_TIMEOUT)
                status = "created"
            else:
                ref.set(copy.deepcopy(data), timeout=IO_TIMEOUT)
                status = "updated" if exists else "created"
        except gexc.AlreadyExists:  # criado por outro processo no meio do caminho
            status = "skipped"
        except (gexc.ServiceUnavailable, gexc.DeadlineExceeded,
                gexc.RetryError) as exc:
            raise SeedError(
                f"Perdi a conexão com o emulador ao gravar {path}. "
                "Confira se o Firestore Emulator continua rodando.", 2) from exc
        except gexc.GoogleAPICallError as exc:
            raise SeedError(f"Falha ao gravar {path}: {exc}", 3) from exc
        log(f"[{status.upper():7}] {path} - {data['name']}")
        results.append((route_id, status))
    return results


# ------------------------------------------------------------------ CLI ----
def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Cadastra rotas de exemplo na coleção 'routes' do "
                    "Firestore Emulator.")
    p.add_argument("--dry-run", action="store_true",
                   help="só valida e mostra o que seria gravado (não conecta)")
    p.add_argument("--skip-existing", action="store_true",
                   help="não sobrescreve documentos que já existem")
    p.add_argument("--only", action="append", metavar="ID",
                   help="grava só a rota indicada (pode repetir)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    args = _parse_args(argv)
    try:
        selected = ROUTES
        if args.only:
            unknown = [r for r in args.only if r not in ROUTES]
            if unknown:
                raise SeedError(
                    f"Rota(s) desconhecida(s): {unknown}. "
                    f"Disponíveis: {sorted(ROUTES)}", 1)
            selected = {r: ROUTES[r] for r in ROUTES if r in args.only}

        problems = validate_routes(selected)
        if problems:
            lines = [f"  - {rid}: {p}" for rid, ps in problems.items() for p in ps]
            raise SeedError("Dados inválidos; nada foi gravado:\n"
                            + "\n".join(lines), 1)

        if args.dry_run:
            print("[DRY-RUN] Dados válidos; nada será conectado nem gravado:")
            for rid, data in selected.items():
                print(f"  {COLLECTION}/{rid} - {data['name']} "
                      f"({len(data['stops'])} parada(s))")
            return 0

        check_project_id(PROJECT_ID)
        host = resolve_emulator_host()
        check_emulator_reachable(host)
        print(f"Firestore Emulator em {host} (projeto {PROJECT_ID})")
        db = make_client(host, PROJECT_ID)
        results = seed_routes(db, selected, skip_existing=args.skip_existing)
        resumo = {s: sum(1 for _, x in results if x == s)
                  for s in ("created", "updated", "skipped")}
        print(f"Concluído: {resumo['created']} criado(s), "
              f"{resumo['updated']} atualizado(s), "
              f"{resumo['skipped']} ignorado(s).")
        return 0
    except SeedError as err:
        print(f"ERRO: {err.message}", file=sys.stderr)
        return err.exit_code


if __name__ == "__main__":
    sys.exit(main())
