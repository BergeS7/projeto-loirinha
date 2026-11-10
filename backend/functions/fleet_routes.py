"""Rotas por frota e associação motorista <-> rota (`drivers.id_route`).

Este módulo NÃO depende do runtime de Cloud Functions: recebe o cliente
Firestore, o UID já autenticado, o payload e as claims do token. As callables
em main.py são cascas finas que traduzem `RouteError` em `HttpsError`
(mesmo padrão de checkin.py e telemetry.py).

MODELO
------
* `routes/{id}.fleet_owner_id` = UID do dono da frota responsável. É gravado
  SOMENTE por `handle_create_route`, com a frota do usuário autenticado; o
  payload não pode trazê-lo. Rotas sem esse campo (ex.: as de
  scripts/seed_routes.py) são "legadas/públicas": continuam existindo, mas NÃO
  pertencem a nenhuma frota e, por isso, não podem ser atribuídas a motoristas.
* `drivers/{id}.id_route` = ID real do documento em `routes`.

AUTORIZAÇÃO
-----------
A role vem EXCLUSIVAMENTE da custom claim `role` (nunca de `users/{uid}.role`).
A frota do dono vem de `users/{uid}.fleet_owner_id` e deve ser o próprio UID
(mesma regra do firestore.rules). Nada de `fleet_owner_id`, `user_id` ou
`id_route` do cliente é confiado: os IDs recebidos só servem para localizar
documentos, e a propriedade é sempre revalidada aqui (o Admin SDK ignora as
Security Rules).
"""

from __future__ import annotations

import math
import re
from typing import Any

from roles import ROLE_DONO_FROTA, ROLE_MOTORISTA, read_role

USERS = "users"
DRIVERS = "drivers"
BUSES = "buses"
ROUTES = "routes"

MAX_ID_LENGTH = 128


class RouteError(Exception):
    """Erro de negócio. `code` usa os valores de `FunctionsErrorCode`;
    `reason` é um identificador estável para o app e para os testes."""

    def __init__(self, code: str, reason: str, message: str):
        super().__init__(message)
        self.code = code
        self.reason = reason
        self.message = message


# ============================================================ validação =====
_PLACE_KEYS = {"name", "latitude", "longitude"}
_STOP_KEYS = _PLACE_KEYS | {"order"}
_COLOR_KEYS = ("color_hex_route", "color_hex_out_route")
# Mesmo esquema de scripts/seed_routes.py (que não é implantado com as
# functions). Um teste garante que os dois validadores concordam.
ROUTE_KEYS = frozenset({"name", "origin", "destination", "stops", *_COLOR_KEYS})
_HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{6}")


def _is_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _check_text(path: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: deve ser texto não vazio")


def _check_coord(path: str, value: Any, limit: float, errors: list[str]) -> None:
    if not _is_number(value):
        errors.append(f"{path}: deve ser número")
    elif not -limit <= value <= limit:
        errors.append(f"{path}: deve estar entre -{limit:g} e {limit:g}")


def _check_place(path: str, place: Any, allowed: set[str],
                 errors: list[str]) -> None:
    if not isinstance(place, dict):
        errors.append(f"{path}: deve ser um objeto")
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


def validate_route_data(data: Any) -> list[str]:
    """Lista de problemas do corpo de uma rota (vazia = válida)."""
    if not isinstance(data, dict):
        return ["rota: deve ser um objeto"]
    errors: list[str] = []
    for key in sorted(ROUTE_KEYS - set(data)):
        errors.append(f"{key}: ausente")
    for key in sorted(str(k) for k in set(data) - ROUTE_KEYS):
        errors.append(f"{key}: campo inesperado")
    if "name" in data:
        _check_text("name", data["name"], errors)
    if "origin" in data:
        _check_place("origin", data["origin"], _PLACE_KEYS, errors)
    if "destination" in data:
        _check_place("destination", data["destination"], _PLACE_KEYS, errors)
    for key in _COLOR_KEYS:
        if key in data and (not isinstance(data[key], str)
                            or not _HEX_COLOR.fullmatch(data[key])):
            errors.append(f"{key}: deve ser cor hexadecimal #RRGGBB")
    if "stops" in data:
        stops = data["stops"]
        if not isinstance(stops, list):
            errors.append("stops: deve ser uma lista")
        else:
            orders: list[int] = []
            for i, stop in enumerate(stops):
                path = f"stops[{i}]"
                _check_place(path, stop, _STOP_KEYS, errors)
                if isinstance(stop, dict) and "order" in stop:
                    order = stop["order"]
                    if (not isinstance(order, int) or isinstance(order, bool)
                            or order <= 0):
                        errors.append(f"{path}.order: deve ser inteiro positivo")
                    else:
                        orders.append(order)
            repeated = sorted({o for o in orders if orders.count(o) > 1})
            if repeated:
                errors.append(f"stops: ordens repetidas {repeated}")
    return errors


# ============================================================ utilidades ====
def _non_empty_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _require_uid(uid: Any) -> str:
    if not uid or not isinstance(uid, str):
        raise RouteError("unauthenticated", "unauthenticated",
                         "É necessário estar autenticado.")
    return uid


def _require_role(claims: Any, expected: str) -> None:
    """Autoriza pela custom claim `role` do token (fail-closed)."""
    role, problem = read_role(claims)
    if problem == "missing":
        raise RouteError("permission-denied", "missing_role_claim",
                         "Usuário sem role definida no token.")
    if problem == "invalid":
        raise RouteError("permission-denied", "invalid_role",
                         "Role do token inválida.")
    if role != expected:
        if expected == ROLE_DONO_FROTA:
            raise RouteError("permission-denied", "not_a_fleet_owner",
                             "Apenas donos de frota podem fazer isto.")
        raise RouteError("permission-denied", "not_a_driver",
                         "Apenas motoristas podem fazer isto.")


def _parse_id(data: Any, key: str, reason: str) -> str:
    raw = data.get(key) if isinstance(data, dict) else None
    value = _non_empty_str(raw)
    if (value is None or len(value) > MAX_ID_LENGTH or "/" in value
            or value in {".", ".."}
            or (value.startswith("__") and value.endswith("__"))):
        raise RouteError("invalid-argument", reason,
                         f"Informe '{key}' válido (texto não vazio, sem '/').")
    return value


def _only_keys(data: Any, allowed: set[str]) -> dict:
    if not isinstance(data, dict):
        raise RouteError("invalid-argument", "invalid_payload",
                         "Envie um objeto JSON.")
    extra = set(data) - allowed
    if extra:
        raise RouteError(
            "invalid-argument", "unexpected_field",
            "Campos não permitidos: "
            + ", ".join(sorted(str(k) for k in extra)) + ".")
    return data


def _owner_fleet(db, uid: str) -> str:
    """Frota do dono autenticado: `users/{uid}.fleet_owner_id`, que deve ser o
    próprio UID (dono de frota = dono da própria frota)."""
    snap = db.collection(USERS).document(uid).get()
    if not snap.exists:
        raise RouteError("not-found", "user_not_found", "Usuário não encontrado.")
    fleet = _non_empty_str((snap.to_dict() or {}).get("fleet_owner_id"))
    if fleet is None or fleet != uid:
        raise RouteError("permission-denied", "fleet_not_owned",
                         "Este usuário não é dono de uma frota.")
    return fleet


def _driver_of_user(db, user_uid: str) -> tuple[str, dict]:
    """Cadastro único de `drivers` do usuário (`user_id == user_uid`)."""
    from google.cloud.firestore_v1.base_query import FieldFilter

    snaps = list(db.collection(DRIVERS)
                 .where(filter=FieldFilter("user_id", "==", user_uid))
                 .limit(2).get())
    if not snaps:
        raise RouteError("permission-denied", "driver_record_not_found",
                         "Motorista sem cadastro em 'drivers'.")
    if len(snaps) > 1:
        raise RouteError("failed-precondition", "duplicate_driver_record",
                         "Cadastro de motorista ambíguo (duplicado).")
    driver = snaps[0].to_dict() or {}
    if driver.get("user_id") != user_uid:
        raise RouteError("permission-denied", "driver_record_not_found",
                         "Motorista sem cadastro em 'drivers'.")
    return snaps[0].id, driver


def _fleet_route(db, route_id: str, fleet: str) -> dict:
    """Rota existente E pertencente à frota `fleet`; senão levanta RouteError."""
    snap = db.collection(ROUTES).document(route_id).get()
    if not snap.exists:
        raise RouteError("not-found", "route_not_found", "Rota não encontrada.")
    route = snap.to_dict() or {}
    route_fleet = _non_empty_str(route.get("fleet_owner_id"))
    if route_fleet is None:
        raise RouteError("permission-denied", "route_without_fleet",
                         "Esta rota não pertence a nenhuma frota.")
    if route_fleet != fleet:
        raise RouteError("permission-denied", "route_other_fleet",
                         "Esta rota pertence a outra frota.")
    return route


def _public_route(route_id: str, route: dict) -> dict:
    body = {k: v for k, v in route.items() if k != "fleet_owner_id"}
    return {"routeId": route_id, **body}


def find_fleet_route_id(db, fleet: str | None,
                        preferred: str | None = None) -> str | None:
    """ID de uma rota REAL da frota, ou None. Usado pelo seed.

    Se `preferred` existe e pertence à frota, é mantido; caso contrário, devolve
    a de menor ID entre as rotas com `fleet_owner_id == fleet`. Nunca devolve
    rota de outra frota nem rota sem frota.
    """
    from google.cloud.firestore_v1.base_query import FieldFilter

    fleet = _non_empty_str(fleet)
    if fleet is None:
        return None
    if _non_empty_str(preferred):
        snap = db.collection(ROUTES).document(preferred).get()
        if snap.exists and (snap.to_dict() or {}).get("fleet_owner_id") == fleet:
            return preferred
    ids = sorted(s.id for s in db.collection(ROUTES)
                 .where(filter=FieldFilter("fleet_owner_id", "==", fleet)).get())
    return ids[0] if ids else None


# ============================================================ dono da frota ==
def handle_create_route(db, uid: Any, data: Any, claims: Any) -> dict:
    """Dono cadastra uma rota NOVA na própria frota (ID gerado pelo Firestore).

    O payload tem exatamente os campos de uma rota; `fleet_owner_id` não é
    aceito do cliente. Não existe edição: nunca sobrescreve rota alheia.
    """
    uid = _require_uid(uid)
    _require_role(claims, ROLE_DONO_FROTA)
    data = _only_keys(data, set(ROUTE_KEYS))
    problems = validate_route_data(data)
    if problems:
        raise RouteError("invalid-argument", "invalid_route",
                         "Rota inválida: " + "; ".join(problems[:10]))
    fleet = _owner_fleet(db, uid)
    ref = db.collection(ROUTES).document()
    body = {**data, "fleet_owner_id": fleet}
    ref.create(body)
    return {"success": True, "routeId": ref.id, "message": "Rota cadastrada."}


def handle_set_driver_route(db, uid: Any, data: Any, claims: Any) -> dict:
    """Dono atribui uma rota da sua frota a um motorista da sua frota.

    Entrada: {"driverId": <ID do doc em drivers>, "routeId": <ID do doc em routes>}.
    """
    uid = _require_uid(uid)
    _require_role(claims, ROLE_DONO_FROTA)
    data = _only_keys(data, {"driverId", "routeId"})
    driver_id = _parse_id(data, "driverId", "invalid_driver_id")
    route_id = _parse_id(data, "routeId", "invalid_route_id")
    fleet = _owner_fleet(db, uid)

    driver_ref = db.collection(DRIVERS).document(driver_id)
    driver_snap = driver_ref.get()
    if not driver_snap.exists:
        raise RouteError("not-found", "driver_not_found",
                         "Motorista não encontrado.")
    if _non_empty_str((driver_snap.to_dict() or {}).get("fleet_owner_id")) != fleet:
        raise RouteError("permission-denied", "driver_other_fleet",
                         "Este motorista pertence a outra frota.")
    _fleet_route(db, route_id, fleet)
    driver_ref.update({"id_route": route_id})
    return {"success": True, "driverId": driver_id, "routeId": route_id,
            "message": "Rota atribuída ao motorista."}


def handle_get_bus_route(db, uid: Any, data: Any, claims: Any) -> dict:
    """Dono consulta a rota do motorista ativo de um ônibus da sua frota.

    Entrada: {"busId": <ID do doc em buses>} (mesmo busId da telemetria).
    """
    uid = _require_uid(uid)
    _require_role(claims, ROLE_DONO_FROTA)
    data = _only_keys(data, {"busId"})
    bus_id = _parse_id(data, "busId", "invalid_bus_id")
    fleet = _owner_fleet(db, uid)

    bus_snap = db.collection(BUSES).document(bus_id).get()
    if not bus_snap.exists:
        raise RouteError("not-found", "bus_not_found", "Ônibus não encontrado.")
    bus = bus_snap.to_dict() or {}
    if _non_empty_str(bus.get("fleet_owner_id")) != fleet:
        raise RouteError("permission-denied", "bus_other_fleet",
                         "Este ônibus pertence a outra frota.")
    active = _non_empty_str(bus.get("active_driver_id"))
    if active is None:
        raise RouteError("failed-precondition", "no_active_driver",
                         "Nenhum motorista está com este ônibus.")
    driver_doc_id, driver = _driver_of_user(db, active)
    if _non_empty_str(driver.get("fleet_owner_id")) != fleet:
        raise RouteError("permission-denied", "driver_other_fleet",
                         "O motorista deste ônibus pertence a outra frota.")
    route_id = _non_empty_str(driver.get("id_route"))
    if route_id is None:
        raise RouteError("failed-precondition", "driver_without_route",
                         "O motorista não tem rota atribuída.")
    route = _fleet_route(db, route_id, fleet)
    return {"success": True, "busId": bus_id, "driverDocId": driver_doc_id,
            "route": _public_route(route_id, route)}


# ============================================================== motorista ====
def handle_get_my_route(db, uid: Any, data: Any, claims: Any) -> dict:
    """Motorista lê SOMENTE a própria rota (`drivers.id_route` do próprio UID).

    Não aceita payload: nenhum ID vindo do cliente participa da consulta.
    """
    uid = _require_uid(uid)
    _require_role(claims, ROLE_MOTORISTA)
    if data not in (None, {}):
        _only_keys(data, set())
    user_snap = db.collection(USERS).document(uid).get()
    if not user_snap.exists:
        raise RouteError("not-found", "user_not_found", "Usuário não encontrado.")
    driver_doc_id, driver = _driver_of_user(db, uid)
    if driver.get("active") is not True:
        raise RouteError("permission-denied", "driver_inactive",
                         "Cadastro de motorista inativo.")
    fleet = _non_empty_str(driver.get("fleet_owner_id"))
    user_fleet = _non_empty_str((user_snap.to_dict() or {}).get("fleet_owner_id"))
    if fleet is None or fleet != user_fleet:
        raise RouteError("permission-denied", "fleet_mismatch_driver_user",
                         "Frota do motorista diverge da frota do usuário.")
    route_id = _non_empty_str(driver.get("id_route"))
    if route_id is None:
        raise RouteError("failed-precondition", "driver_without_route",
                         "Você não tem rota atribuída.")
    route = _fleet_route(db, route_id, fleet)
    return {"success": True, "driverDocId": driver_doc_id,
            "route": _public_route(route_id, route)}
