"""Telemetria GPS dos ônibus no Realtime Database: /telemetry/{bus_id}.

Este módulo NÃO depende do runtime de Cloud Functions nem importa
`firebase_admin` no topo: recebe referências já prontas (`root` = referência
Admin SDK de `/telemetry`; `db` = cliente Firestore). Isso permite testá-lo
contra os emuladores e a lógica pura contra um backend em memória.

MODELO (uma única fonte de verdade)
-----------------------------------
* O vínculo motorista <-> ônibus <-> frota continua SENDO o do Firestore
  (`buses/{id}.active_driver_id`, `drivers/*`, escritos pelo `checkIn`). O RTDB
  guarda apenas a posição/saúde de conexão; nada de negócio é duplicado.
* Os clientes NÃO escrevem no RTDB (regras negam tudo). Todo envio passa por
  `handle_send_telemetry`, que autoriza no Firestore e grava via Admin SDK.

TIMESTAMPS
----------
* `updated_at` = hora do SERVIDOR no recebimento (ms Unix). É a única medida
  usada para decidir online/offline. Relógio errado ou manipulado no celular
  não consegue mantê-lo "online".
* `captured_at` (opcional no envio) = hora do fix medida pelo celular. Serve só
  para rejeitar fix ATRASADO (> 45 s), do FUTURO (> 10 s) ou FORA DE ORDEM
  (<= ao último aceito). Se ausente, usa-se a hora do servidor.

CONCORRÊNCIA
------------
Toda escrita é compare-and-swap por ETag (`get(etag=True)` +
`set_if_unchanged`), com nova leitura em caso de conflito. Assim, o monitor
nunca sobrescreve uma telemetria que chegou depois da sua leitura, e uma
atualização atrasada nunca sobrescreve uma mais nova.

POSIÇÃO ANTERIOR
----------------
`lat_anterior`/`long_anterior` = `lat`/`lng` do nó lido na MESMA leitura com
ETag que o CAS protege: a cópia atual -> anterior e a gravação da posição nova
são uma única escrita condicional, então atualizações concorrentes não perdem
nem duplicam a posição anterior. Na primeira atualização (ou se o nó antigo não
tem coordenadas válidas) os campos são OMITIDOS (o RTDB não guarda null).
Fixes recusados (inválidos/atrasados/antigos) não tocam no nó.

VELOCIDADE
----------
`speed` = leitura INSTANTÂNEA do GPS do celular, em km/h, armazenada como
inteiro (arredondamento para o mais próximo; .5 sobe). Não é velocidade média.

FIM DE VIAGEM x PERDA DE CONEXÃO
--------------------------------
`status` não tem valor "fora de serviço" (só in_service/delayed/out_of_route).
Fora de serviço = NÃO HÁ NÓ: `endTelemetry` remove o nó e o monitor também o
remove quando o Firestore diz que o ônibus não tem motorista ativo. Só
veículos em serviço podem ficar `connection_lost`.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from roles import ROLE_MOTORISTA, read_role

BUSES = "buses"
DRIVERS = "drivers"

# --- Regras de tempo -------------------------------------------------------
OFFLINE_THRESHOLD_MS = 45_000          # perda de conexão se idade  >  45 s
MAX_FIX_AGE_MS = OFFLINE_THRESHOLD_MS  # fix mais velho que isso é "atrasado"
FUTURE_TOLERANCE_MS = 10_000           # tolerância de relógio do celular
MAX_CAS_RETRIES = 10

# --- Domínio ---------------------------------------------------------------
STATUSES = ("in_service", "delayed", "out_of_route")
CONNECTION_ONLINE = "online"
CONNECTION_LOST = "connection_lost"

SPEED_MAX_KMH = 200.0
DISTANCE_MAX_KM = 20_000.0
BUS_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Contrato estrito: qualquer outro campo (is_online, connection_status,
# updated_at, uid, role...) é recusado em vez de ignorado em silêncio.
ALLOWED_INPUT_KEYS = frozenset(
    {"busId", "lat", "lng", "speed", "heading", "status", "captured_at",
     "distance"})


class TelemetryError(Exception):
    """Erro de negócio. `code` usa os valores de `FunctionsErrorCode`;
    `reason` é um identificador estável para o app e para os testes."""

    def __init__(self, code: str, reason: str, message: str):
        super().__init__(message)
        self.code = code
        self.reason = reason


def now_ms() -> int:
    return int(time.time() * 1000)


# ============================================================ validação =====
def _finite_number(value: Any) -> bool:
    # bool é subclasse de int em Python: precisa ser excluído explicitamente.
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _as_ms(value: Any) -> int | None:
    """Inteiro positivo em ms, ou None. Aceita float integral (JSON de JS)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int) and value > 0:
        return value
    return None


def _bad(reason: str, message: str) -> TelemetryError:
    return TelemetryError("invalid-argument", reason, message)


def parse_bus_id(raw: Any) -> str:
    if not isinstance(raw, str) or not BUS_ID_RE.match(raw):
        raise _bad("invalid_bus_id",
                   "'busId' inválido (1-64 caracteres: letras, números, _ e -).")
    return raw


def parse_payload(data: Any) -> dict:
    """Valida o payload do celular. Devolve
    {bus_id, lat, lng, speed, heading, status, captured_at|None}."""
    if not isinstance(data, dict):
        raise _bad("invalid_payload", "Envie um objeto JSON.")
    extra = set(data) - ALLOWED_INPUT_KEYS
    if extra:
        raise _bad("unexpected_field",
                   "Campos não permitidos: "
                   + ", ".join(sorted(str(k) for k in extra)) + ".")
    bus_id = parse_bus_id(data.get("busId"))

    lat, lng = data.get("lat"), data.get("lng")
    if not _finite_number(lat) or not -90 <= lat <= 90:
        raise _bad("invalid_lat", "'lat' deve ser número finito em [-90, 90].")
    if not _finite_number(lng) or not -180 <= lng <= 180:
        raise _bad("invalid_lng", "'lng' deve ser número finito em [-180, 180].")
    if lat == 0 and lng == 0:
        # "Null island": valor típico de GPS sem fix; não é posição plausível.
        raise _bad("null_island", "Coordenadas (0, 0) não são uma posição válida.")

    speed = data.get("speed")
    if not _finite_number(speed) or not 0 <= speed <= SPEED_MAX_KMH:
        raise _bad("invalid_speed",
                   f"'speed' deve ser número finito em [0, {SPEED_MAX_KMH:g}] km/h.")
    heading = data.get("heading")
    if not _finite_number(heading) or not 0 <= heading < 360:
        raise _bad("invalid_heading", "'heading' deve estar em [0, 359].")
    status = data.get("status")
    if not isinstance(status, str) or status not in STATUSES:
        raise _bad("invalid_status",
                   "'status' deve ser um de: " + ", ".join(STATUSES) + ".")

    # `distance` (km, opcional): distância HIPOTÉTICA informada no envio. Não é
    # a distância de um passageiro real (ver scripts/distance_decay.py).
    distance = data.get("distance")
    if distance is not None and (not _finite_number(distance)
                                 or not 0 <= distance <= DISTANCE_MAX_KM):
        raise _bad("invalid_distance",
                   f"'distance' deve ser número finito em [0, {DISTANCE_MAX_KM:g}] km.")

    captured_at = data.get("captured_at")
    if captured_at is not None:
        captured_at = _as_ms(captured_at)
        if captured_at is None:
            raise _bad("invalid_captured_at",
                       "'captured_at' deve ser timestamp Unix em ms (inteiro > 0).")
    return {"bus_id": bus_id, "lat": lat, "lng": lng, "speed": speed,
            "heading": heading, "status": status, "captured_at": captured_at,
            "distance": distance}


def round_speed_kmh(speed: float) -> int:
    """km/h -> inteiro mais próximo (.5 sobe). `speed` já validado (>= 0)."""
    return int(math.floor(speed + 0.5))


def _valid_coords(lat: Any, lng: Any) -> bool:
    return (_finite_number(lat) and _finite_number(lng)
            and -90 <= lat <= 90 and -180 <= lng <= 180)


# ---------------------------------------------- cálculos (funções puras) -----
EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distância geográfica em linha reta (grande círculo), em km.

    NÃO é distância de percurso nem distância percorrida pelo ônibus.
    """
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def eta_minutes(distance_km: Any, speed_kmh: Any) -> int | None:
    """Tempo estimado de chegada em minutos inteiros, ou None.

    minutos = distância_km / velocidade_kmh * 60 (arredondado ao mais próximo).
    Estimativa SIMPLIFICADA: linha reta, velocidade instantânea constante, sem
    trânsito, paradas, desvios nem percurso real. Entrada inválida ou
    velocidade <= 0 -> None (nunca uma previsão numérica enganosa).
    """
    if not _finite_number(distance_km) or distance_km < 0:
        return None
    if not _finite_number(speed_kmh) or speed_kmh <= 0:
        return None
    return int(math.floor(distance_km / speed_kmh * 60 + 0.5))


def predicted_arrival_ms(server_now_ms: int, eta_min: int | None) -> int | None:
    """Horário previsto (Unix ms, UTC) = instante do SERVIDOR + ETA. None se
    não há ETA."""
    if eta_min is None or isinstance(eta_min, bool) or not isinstance(eta_min, int):
        return None
    return server_now_ms + eta_min * 60_000


def _effective_captured_at(fix: dict, server_now: int) -> int:
    captured = fix.get("captured_at")
    if captured is None:
        return server_now
    if captured > server_now + FUTURE_TOLERANCE_MS:
        raise TelemetryError(
            "invalid-argument", "captured_at_in_future",
            "O horário do fix está no futuro (relógio do aparelho incorreto?).")
    if server_now - captured > MAX_FIX_AGE_MS:
        raise TelemetryError(
            "failed-precondition", "stale_fix",
            "Fix atrasado (mais de 45 s): não conta como heartbeat.")
    return captured


# ============================================================ escrita =======
def _next_node(prev: Any, fix: dict, server_now: int) -> dict:
    """Calcula o novo nó. Levanta TelemetryError se o fix deve ser recusado."""
    captured = _effective_captured_at(fix, server_now)
    updated_at = server_now
    if isinstance(prev, dict):
        prev_captured = _as_ms(prev.get("captured_at"))
        if prev_captured is not None and captured <= prev_captured:
            raise TelemetryError(
                "failed-precondition", "stale_update",
                "Atualização mais antiga (ou repetida) que a já registrada.")
        prev_updated = _as_ms(prev.get("updated_at"))
        if prev_updated is not None and prev_updated > updated_at:
            updated_at = prev_updated  # nunca regride (skew entre instâncias)
    node = {
        "lat": fix["lat"], "lng": fix["lng"],
        "speed": round_speed_kmh(fix["speed"]),  # km/h inteiro
        "heading": fix["heading"], "status": fix["status"],
        "updated_at": updated_at,
        "is_online": True, "connection_status": CONNECTION_ONLINE,
        "captured_at": captured,
    }
    if fix.get("distance") is not None:
        node["distance"] = fix["distance"]  # km; ausente = não gravado
    if isinstance(prev, dict) and _valid_coords(prev.get("lat"), prev.get("lng")):
        node["lat_anterior"] = prev["lat"]
        node["long_anterior"] = prev["lng"]
    return node


def apply_update(root, fix: dict, server_now: int) -> dict:
    """Grava um fix JÁ validado em /telemetry/{bus_id} (CAS por ETag).

    Substitui só o nó do veículo; os demais ficam intactos. Atualização
    inválida/atrasada/antiga levanta erro e NÃO toca no nó (logo, não conta
    como heartbeat nem restaura o estado online).
    """
    ref = root.child(fix["bus_id"])
    for _ in range(MAX_CAS_RETRIES):
        prev, etag = ref.get(etag=True)
        node = _next_node(prev, fix, server_now)
        ok, _, _ = ref.set_if_unchanged(etag, node)
        if ok:
            return node
    raise TelemetryError("aborted", "contention",
                         "Muita concorrência neste veículo; tente novamente.")


# ============================================================ autorização ===
def _require_driver_role(claims: Any) -> None:
    role, problem = read_role(claims)
    if problem == "missing":
        raise TelemetryError("permission-denied", "missing_role_claim",
                             "Usuário sem role definida no token.")
    if problem == "invalid":
        raise TelemetryError("permission-denied", "invalid_role",
                             "Role do token inválida.")
    if role != ROLE_MOTORISTA:
        raise TelemetryError("permission-denied", "not_a_driver",
                             "Apenas motoristas enviam telemetria.")


def _non_empty_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def authorize_driver(db, uid: str, bus_id: str) -> None:
    """O motorista só opera o ônibus em que fez check-in, na própria frota.

    Fonte de verdade: Firestore (`buses`, `drivers`), o mesmo modelo do
    `checkIn`. O cadastro é relido a cada envio: motorista desativado perde o
    acesso na hora.
    """
    from google.cloud.firestore_v1.base_query import FieldFilter

    bus_snap = db.collection(BUSES).document(bus_id).get()
    if not bus_snap.exists:
        raise TelemetryError("not-found", "bus_not_found", "Ônibus não encontrado.")
    bus = bus_snap.to_dict() or {}
    if bus.get("active_driver_id") != uid:
        raise TelemetryError("permission-denied", "not_active_driver",
                             "Você não está em check-in neste ônibus.")

    drivers = list(db.collection(DRIVERS)
                   .where(filter=FieldFilter("user_id", "==", uid))
                   .limit(2).get())
    if len(drivers) == 0:
        raise TelemetryError("permission-denied", "driver_record_not_found",
                             "Motorista sem cadastro em 'drivers'.")
    if len(drivers) > 1:
        raise TelemetryError("failed-precondition", "duplicate_driver_record",
                             "Cadastro de motorista ambíguo (duplicado).")
    driver = drivers[0].to_dict() or {}
    if driver.get("active") is not True:
        raise TelemetryError("permission-denied", "driver_inactive",
                             "Cadastro de motorista inativo.")
    fleet = _non_empty_str(driver.get("fleet_owner_id"))
    if fleet is None or fleet != _non_empty_str(bus.get("fleet_owner_id")):
        raise TelemetryError("permission-denied", "bus_other_fleet",
                             "Este ônibus pertence a outra frota.")


def _check_caller(uid: Any, claims: Any) -> None:
    if not uid or not isinstance(uid, str):
        raise TelemetryError("unauthenticated", "unauthenticated",
                             "É necessário estar autenticado.")
    _require_driver_role(claims)


def handle_send_telemetry(db, root, uid, data, claims,
                          server_now: int | None = None) -> dict:
    """Ponto de entrada de `sendTelemetry`. uid/claims vêm SEMPRE do token."""
    _check_caller(uid, claims)
    fix = parse_payload(data)
    server_now = now_ms() if server_now is None else server_now
    authorize_driver(db, uid, fix["bus_id"])
    node = apply_update(root, fix, server_now)
    return {"success": True, "busId": fix["bus_id"],
            "updated_at": node["updated_at"], "is_online": True,
            "connection_status": CONNECTION_ONLINE}


def handle_end_telemetry(db, root, uid, data, claims) -> dict:
    """Fim normal de viagem: remove o nó (veículo fora de serviço)."""
    _check_caller(uid, claims)
    bus_id = parse_bus_id(data.get("busId") if isinstance(data, dict) else None)
    authorize_driver(db, uid, bus_id)
    ref = root.child(bus_id)
    existed = ref.get() is not None
    ref.delete()
    return {"success": True, "busId": bus_id, "removed": existed}


# ============================================================ monitor =======
def _is_stale(node: dict, server_now: int) -> bool:
    updated = _as_ms(node.get("updated_at"))
    if updated is None:
        return True  # nó corrompido: não pode ser considerado "online"
    return server_now - updated > OFFLINE_THRESHOLD_MS


def expire_node(root, bus_id: str, server_now: int,
                in_service: Callable[[str], bool] | None = None,
                *, _after_read: Callable[[], None] | None = None) -> str:
    """Reavalia UM nó candidato. Devolve:
    "lost" | "removed" | "fresh" | "unchanged" | "gone" | "ignored".

    A decisão é sempre tomada sobre a leitura MAIS RECENTE e a escrita é
    condicionada ao ETag dessa leitura: se chegou telemetria no meio, o CAS
    falha, relê, vê o nó fresco e não escreve nada.
    `_after_read` é um gancho só para testes (simula a chegada concorrente).
    """
    ref = root.child(bus_id)
    for _ in range(MAX_CAS_RETRIES):
        cur, etag = ref.get(etag=True)
        if _after_read is not None:
            hook, _after_read = _after_read, None  # só na 1ª leitura
            hook()
        if cur is None:
            return "gone"
        if not isinstance(cur, dict):
            return "ignored"
        if not _is_stale(cur, server_now):
            return "fresh"
        if in_service is not None and not in_service(bus_id):
            # Viagem encerrada (sem motorista ativo): não é perda de conexão.
            ref.delete()
            return "removed"
        if (cur.get("is_online") is False
                and cur.get("connection_status") == CONNECTION_LOST):
            return "unchanged"
        new = dict(cur)
        new["is_online"] = False
        new["connection_status"] = CONNECTION_LOST
        ok, _, _ = ref.set_if_unchanged(etag, new)
        if ok:
            return "lost"
    raise TelemetryError("aborted", "contention",
                         "Muita concorrência neste veículo; tente novamente.")


@dataclass
class SweepResult:
    now_ms: int
    checked: int = 0
    marked_lost: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def sweep(root, server_now: int,
          in_service: Callable[[str], bool] | None = None) -> SweepResult:
    """Uma varredura central de TODOS os veículos (sem tarefa por veículo).

    Consulta indexada (`.indexOn: updated_at`) traz só os candidatos com idade
    > 45 s (updated_at < now-45000; nós sem `updated_at` válido também vêm,
    pois null ordena primeiro). Em regime normal, retorna ~0 linhas.
    """
    result = SweepResult(now_ms=server_now)
    cutoff = server_now - OFFLINE_THRESHOLD_MS
    candidates = root.order_by_child("updated_at").end_at(cutoff - 1).get()
    if isinstance(candidates, list):  # chaves numéricas viram lista no RTDB
        candidates = {str(i): v for i, v in enumerate(candidates) if v is not None}
    for bus_id in (candidates or {}):
        result.checked += 1
        try:
            outcome = expire_node(root, bus_id, server_now, in_service)
        except Exception as exc:  # um veículo com problema não para os demais
            result.errors.append((bus_id, repr(exc)))
            continue
        if outcome == "lost":
            result.marked_lost.append(bus_id)
        elif outcome == "removed":
            result.removed.append(bus_id)
    return result


def run_sweeps(root, in_service=None, *, iterations: int | None = None,
               interval_s: float = 5.0, clock_ms: Callable[[], int] = now_ms,
               sleep: Callable[[float], None] = time.sleep,
               on_result: Callable[[SweepResult], None] | None = None
               ) -> SweepResult | None:
    """Repete `sweep` a cada `interval_s` (para sempre se iterations=None).

    Uma falha de rede/emulador numa rodada vira `errors` e a próxima rodada
    tenta de novo (o processo não morre).
    """
    last = None
    done = 0
    while iterations is None or done < iterations:
        t = clock_ms()
        try:
            last = sweep(root, t, in_service)
        except Exception as exc:
            last = SweepResult(now_ms=t, errors=[("*", repr(exc))])
        if on_result is not None:
            on_result(last)
        done += 1
        if iterations is not None and done >= iterations:
            break
        sleep(interval_s)
    return last


def firestore_in_service_checker(db) -> Callable[[str], bool]:
    """True se o ônibus existe e tem motorista ativo (viagem em andamento)."""
    def check(bus_id: str) -> bool:
        snap = db.collection(BUSES).document(bus_id).get()
        if not snap.exists:
            return False
        return _non_empty_str((snap.to_dict() or {}).get("active_driver_id")) is not None
    return check
