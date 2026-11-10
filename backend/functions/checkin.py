"""Lógica de check-in de motoristas em ônibus.

Este módulo NÃO depende do runtime de Cloud Functions: recebe um cliente
Firestore, o UID já autenticado e o payload. Isso permite testá-lo diretamente
contra o Firestore Emulator. A função callable `checkIn` (main.py) é apenas uma
casca fina que extrai o UID da autenticação e traduz `CheckInError` em
`HttpsError`.

AUTORIZAÇÃO POR ROLE: a role vem EXCLUSIVAMENTE da custom claim `role` do ID
token verificado (`req.auth.token`), nunca do payload nem de `users/{uid}.role`
(campo apenas informativo/legado). O documento `users/{uid}` continua sendo
lido, mas só para obter `fleet_owner_id` (dado de negócio).

Um motorista ocupa no máximo UM ônibus: ao fazer check-in em um novo ônibus,
qualquer tag antiga ainda vinculada a ele (`active_driver_id == uid`) é
desvinculada (`active_driver_id = None`) na MESMA transação do check-in.

O check-out (fim de expediente) libera os ônibus do próprio motorista. Sem ele,
um ônibus ocupado nunca voltaria a ficar livre e, com a frota toda ocupada,
ninguém conseguiria fazer check-in. Como o check-in, exige a claim `role` =
motorista, mas NÃO exige cadastro ativo em `drivers`: um motorista desativado
depois do check-in ainda consegue liberar o próprio ônibus.

IMPORTANTE: o Admin SDK ignora as Firestore Security Rules. Por isso toda a
validação de identidade, perfil, frota e estado do ônibus é feita aqui.
"""

from __future__ import annotations

import random
import time
from typing import Any

from google.api_core import exceptions as gexc
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from roles import ROLE_MOTORISTA, read_role

USERS = "users"
DRIVERS = "drivers"
BUSES = "buses"

MAX_TAG_LENGTH = 128

# Contenção: o cliente Firestore já tenta a transação até 5 vezes, sem espera.
# Se todas abortarem, ele levanta ValueError (com Aborted como causa). Aqui
# fazemos algumas rodadas externas com espera aleatória crescente para desfazer
# o "passo sincronizado" entre transações concorrentes.
CONTENTION_ROUNDS = 4
CONTENTION_BACKOFF_BASE = 0.15  # segundos; multiplicado pela rodada e por jitter


class CheckInError(Exception):
    """Erro de negócio do check-in.

    `code` usa os mesmos valores de `https_fn.FunctionsErrorCode`
    (ex.: "permission-denied"); `reason` é um identificador estável e legível
    por máquina, útil para o app cliente e para os testes.
    """

    def __init__(self, code: str, reason: str, message: str):
        super().__init__(message)
        self.code = code
        self.reason = reason
        self.message = message


def _non_empty_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _parse_tag_code(data: Any) -> str:
    raw = data.get("tagCode") if isinstance(data, dict) else None
    tag = _non_empty_str(raw)
    if tag is None or len(tag) > MAX_TAG_LENGTH:
        raise CheckInError(
            "invalid-argument", "invalid_tag_code",
            "Informe um 'tagCode' válido (texto não vazio).",
        )
    return tag


def _buses_of_driver(transaction, db, uid: str, exclude_id: str | None = None) -> list:
    """Ônibus vinculados ao motorista (`active_driver_id == uid`), ordenados por ID.

    Leitura transacional: deve ser chamada antes de qualquer gravação.
    """
    snaps = (
        db.collection(BUSES)
        .where(filter=FieldFilter("active_driver_id", "==", uid))
        .get(transaction=transaction)
    )
    return sorted((snap for snap in snaps if snap.id != exclude_id),
                  key=lambda snap: snap.id)


def _released(snaps: list) -> list[dict]:
    return [{"busId": snap.id, "tagCode": (snap.to_dict() or {}).get("tag_code")}
            for snap in snaps]


@firestore.transactional
def _check_in_transaction(transaction, db, uid: str, tag_code: str) -> dict:
    """Valida tudo e grava dentro de UMA transação.

    Regras do Firestore para transações: todas as leituras antes das
    gravações. Se outro motorista confirmar a gravação no mesmo ônibus entre a
    leitura e o commit, o commit é abortado, a função é reexecutada, o ônibus
    aparece ocupado e o check-in é recusado.
    """
    # ---- Leituras -------------------------------------------------------
    user_snap = db.collection(USERS).document(uid).get(transaction=transaction)
    driver_snaps = list(
        db.collection(DRIVERS)
        .where(filter=FieldFilter("user_id", "==", uid))
        .limit(2)
        .get(transaction=transaction)
    )
    bus_snaps = list(
        db.collection(BUSES)
        .where(filter=FieldFilter("tag_code", "==", tag_code))
        .limit(2)
        .get(transaction=transaction)
    )

    # ---- Usuário (dados de negócio: fleet_owner_id) ---------------------
    if not user_snap.exists:
        raise CheckInError("not-found", "user_not_found",
                           "Usuário não encontrado.")
    user = user_snap.to_dict() or {}
    # A role NÃO é verificada aqui: já foi autorizada pela claim do token em
    # handle_check_in. `user["role"]` (se existir) é informativo e ignorado.

    # ---- Cadastro de motorista ------------------------------------------
    if len(driver_snaps) == 0:
        raise CheckInError("permission-denied", "driver_record_not_found",
                           "Motorista sem cadastro em 'drivers'.")
    if len(driver_snaps) > 1:
        raise CheckInError("failed-precondition", "duplicate_driver_record",
                           "Cadastro de motorista ambíguo (duplicado).")
    driver = driver_snaps[0].to_dict() or {}
    if driver.get("user_id") != uid:  # defesa extra; a query já filtra
        raise CheckInError("permission-denied", "driver_record_not_found",
                           "Motorista sem cadastro em 'drivers'.")
    if driver.get("active") is not True:
        raise CheckInError("permission-denied", "driver_inactive",
                           "Cadastro de motorista inativo.")

    fleet = _non_empty_str(driver.get("fleet_owner_id"))
    user_fleet = _non_empty_str(user.get("fleet_owner_id"))
    if fleet is None or user_fleet is None or fleet != user_fleet:
        raise CheckInError("permission-denied", "fleet_mismatch_driver_user",
                           "Frota do motorista diverge da frota do usuário.")

    # ---- Ônibus ---------------------------------------------------------
    if len(bus_snaps) == 0:
        raise CheckInError("not-found", "bus_not_found",
                           "Nenhum ônibus encontrado para esse tagCode.")
    if len(bus_snaps) > 1:
        raise CheckInError("failed-precondition", "duplicate_tag_code",
                           "tagCode ambíguo: mais de um ônibus encontrado.")
    bus_snap = bus_snaps[0]
    bus = bus_snap.to_dict() or {}

    if _non_empty_str(bus.get("fleet_owner_id")) != fleet:
        raise CheckInError("permission-denied", "bus_other_fleet",
                           "Este ônibus pertence a outra frota.")

    current = bus.get("active_driver_id")
    if current not in (None, ""):
        reason = "already_checked_in_here" if current == uid else "bus_occupied"
        message = ("Você já está com este ônibus."
                   if current == uid else
                   "Ônibus já está em uso por outro motorista.")
        raise CheckInError("failed-precondition", reason, message)

    # ---- Tags antigas do motorista ---------------------------------------
    # Só chegamos aqui com o check-in já validado: se qualquer regra acima
    # recusar, nenhum vínculo antigo é tocado. Esta leitura ainda precisa vir
    # antes de qualquer gravação (regra das transações do Firestore).
    stale_snaps = _buses_of_driver(transaction, db, uid, exclude_id=bus_snap.id)

    # ---- Gravação -------------------------------------------------------
    for stale in stale_snaps:
        transaction.update(stale.reference, {"active_driver_id": None})
    transaction.update(bus_snap.reference, {"active_driver_id": uid})

    return {
        "success": True,
        "busId": bus_snap.id,
        "tagCode": tag_code,
        "plate": bus.get("plate"),
        "driverDocId": driver_snaps[0].id,
        "driverId": uid,
        "releasedBuses": _released(stale_snaps),
        "message": "Check-in realizado com sucesso.",
    }


def _is_contention(exc: BaseException) -> bool:
    """True se `exc` é conflito/abort de transação (e não um bug qualquer).

    O cliente Firestore, ao esgotar as tentativas, levanta
    ``ValueError("Failed to commit transaction in N attempts")`` com o
    ``Aborted`` original em ``__cause__``. Qualquer outro ValueError NÃO é
    contenção e deve continuar propagando.
    """
    if isinstance(exc, (gexc.Aborted, gexc.RetryError)):
        return True
    return isinstance(exc, ValueError) and isinstance(
        exc.__cause__, (gexc.Aborted, gexc.RetryError))


@firestore.transactional
def _check_out_transaction(transaction, db, uid: str) -> dict:
    """Libera, numa única transação, todos os ônibus vinculados ao motorista.

    Só toca em ônibus com `active_driver_id == uid`; apenas esse campo muda.
    """
    snaps = _buses_of_driver(transaction, db, uid)
    for snap in snaps:
        transaction.update(snap.reference, {"active_driver_id": None})
    return {
        "success": True,
        "driverId": uid,
        "releasedBuses": _released(snaps),
        "message": ("Check-out realizado com sucesso." if snaps
                    else "Nenhum ônibus vinculado a você."),
    }


def _require_driver_role(claims: Any, action: str = "check-in") -> None:
    """Autoriza pela custom claim `role` do token (fail-closed)."""
    role, problem = read_role(claims)
    if problem == "missing":
        raise CheckInError("permission-denied", "missing_role_claim",
                           "Usuário sem role definida no token.")
    if problem == "invalid":
        raise CheckInError("permission-denied", "invalid_role",
                           "Role do token inválida.")
    if role != ROLE_MOTORISTA:
        raise CheckInError("permission-denied", "not_a_driver",
                           f"Apenas motoristas podem fazer {action}.")


def _require_uid(uid: str | None) -> str:
    if not uid or not isinstance(uid, str):
        raise CheckInError("unauthenticated", "unauthenticated",
                           "É necessário estar autenticado.")
    return uid


def _run_with_contention_retry(transaction_fn, db: firestore.Client, *args) -> dict:
    """Executa `transaction_fn(transaction, db, *args)` com retry de contenção.

    Nova transação a cada rodada; CheckInError (regra de negócio) não é
    capturada aqui e propaga direto.
    """
    for round_no in range(1, CONTENTION_ROUNDS + 1):
        try:
            return transaction_fn(db.transaction(), db, *args)
        except Exception as exc:  # noqa: BLE001 - reclassificamos abaixo
            if not _is_contention(exc):
                raise
            if round_no == CONTENTION_ROUNDS:
                raise CheckInError(
                    "aborted", "contention",
                    "Muita concorrência neste ônibus; tente novamente.",
                ) from exc
            time.sleep(random.uniform(0.5, 1.5) * CONTENTION_BACKOFF_BASE * round_no)

    # Inalcançável (o laço sempre retorna ou levanta); mantém o tipo de retorno.
    raise CheckInError("aborted", "contention",
                       "Muita concorrência neste ônibus; tente novamente.")


def handle_check_in(db: firestore.Client, uid: str | None, data: Any,
                    claims: Any) -> dict:
    """Ponto de entrada.

    `uid` e `claims` devem vir SEMPRE do token verificado (`req.auth.uid` e
    `req.auth.token`). Nada do payload (`data`) é usado para identidade/role.
    """
    uid = _require_uid(uid)
    tag_code = _parse_tag_code(data)
    _require_driver_role(claims)
    return _run_with_contention_retry(_check_in_transaction, db, uid, tag_code)


def handle_check_out(db: firestore.Client, uid: str | None, claims: Any) -> dict:
    """Fim de expediente: libera os ônibus do motorista autenticado.

    `uid` e `claims` devem vir SEMPRE do token verificado (`req.auth.uid` e
    `req.auth.token`); não há payload. Exige a claim `role` = motorista, mas
    não consulta `drivers`/`active`: um motorista desativado depois do
    check-in ainda libera o próprio ônibus. Só ônibus com
    `active_driver_id == uid` são tocados. Idempotente: sem ônibus vinculado,
    devolve sucesso com `releasedBuses` vazio.
    """
    uid = _require_uid(uid)
    _require_driver_role(claims, "check-out")
    return _run_with_contention_retry(_check_out_transaction, db, uid)
