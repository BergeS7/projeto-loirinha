"""Contas: passageiro por autoatendimento; motorista somente pelo dono da própria frota.

Não existe endpoint para elevar alguém a dono. O primeiro dono é provisionado
por administração confiável. Auth e Firestore não têm transação distribuída;
criação de motorista compensa falha de persistência removendo a conta nova.
"""

import secrets
from google.cloud.firestore_v1.base_query import FieldFilter
from firebase_admin import auth
from fleet_routes import (
    RouteError,
    _require_uid,
    _require_role,
    _owner_fleet,
    _only_keys,
)
from roles import ROLE_DONO_FROTA


def text(data, key, maximum=120):
    """Recusa texto ausente, vazio ou excessivo antes de tocar nos serviços."""
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise RouteError(
            "invalid-argument", "invalid_account", "Confira os dados da conta."
        )
    return value.strip()


def owner(db, uid, claims):
    """Identidade, claim e vínculo da frota precisam concordar no servidor."""
    uid = _require_uid(uid)
    _require_role(claims, ROLE_DONO_FROTA)
    return _owner_fleet(db, uid)


def register_passenger(db, uid, data, claims):
    """Conclui conta de e-mail já autenticada sem aceitar papel ou frota do cliente."""
    uid = _require_uid(uid)
    data = _only_keys(data, {"name"})
    name = text(data, "name")
    record = auth.get_user(uid)
    existing_claims = dict(record.custom_claims or {})
    if existing_claims.get("role") not in (None, "passageiro") or not record.email:
        raise RouteError(
            "permission-denied",
            "invalid_role",
            "Esta conta não pode ser cadastrada como passageiro.",
        )
    reference = db.collection("users").document(uid)
    # Uma conta operacional não é sobrescrita, mesmo com token antigo sem claim.
    existing = reference.get().to_dict() or {}
    if existing.get("fleet_owner_id"):
        raise RouteError(
            "permission-denied", "invalid_role", "Conta operacional protegida."
        )
    reference.set({"name": name, "email": record.email, "role": "passageiro"})
    auth.set_custom_user_claims(uid, {**existing_claims, "role": "passageiro"})
    return {"success": True}


def list_users(db, uid, data, claims):
    """Lista somente motoristas da frota solicitante; não expõe o diretório global."""
    fleet = owner(db, uid, claims)
    _only_keys(data or {}, set())
    users = []
    for snapshot in (
        db.collection("drivers")
        .where(filter=FieldFilter("fleet_owner_id", "==", fleet))
        .limit(101)
        .stream()
    ):
        driver = snapshot.to_dict()
        profile = (
            db.collection("users").document(driver["user_id"]).get().to_dict() or {}
        )
        # Só copia dados de perfil quando o vínculo também confere.
        if profile.get("fleet_owner_id") != fleet:
            continue
        users.append(
            {
                "id": snapshot.id,
                "name": profile.get("name", "Motorista"),
                "email": profile.get("email", ""),
                "active": driver.get("active") is True,
                "routeId": driver.get("id_route"),
            }
        )
    return {"users": users[:100], "hasMore": len(users) > 100}


def create_driver(db, uid, data, claims):
    """Cria motorista sem devolver senha; o titular define-a por recuperação de e-mail."""
    fleet = owner(db, uid, claims)
    data = _only_keys(data, {"name", "email"})
    name, email = text(data, "name"), text(data, "email", 254)
    try:
        record = auth.create_user(
            email=email, display_name=name, password=secrets.token_urlsafe(32)
        )
    except (ValueError, auth.EmailAlreadyExistsError) as error:
        raise RouteError(
            "invalid-argument", "invalid_account", "E-mail inválido ou já cadastrado."
        ) from error
    try:
        auth.set_custom_user_claims(record.uid, {"role": "motorista"})
        batch = db.batch()
        batch.set(
            db.collection("users").document(record.uid),
            {
                "name": name,
                "email": email,
                "role": "motorista",
                "fleet_owner_id": fleet,
            },
        )
        batch.set(
            db.collection("drivers").document(record.uid),
            {
                "user_id": record.uid,
                "fleet_owner_id": fleet,
                "active": True,
                "driver_code": record.uid,
            },
        )
        batch.commit()
    except Exception:
        auth.delete_user(record.uid)
        raise
    return {"success": True, "driverId": record.uid}


def list_routes(db, uid, data, claims):
    """Opções do seletor de rotas limitadas à frota autenticada."""
    fleet = owner(db, uid, claims)
    _only_keys(data or {}, set())
    snapshots = (
        db.collection("routes")
        .where(filter=FieldFilter("fleet_owner_id", "==", fleet))
        .limit(100)
        .stream()
    )
    return {
        "routes": [
            {"id": snapshot.id, "name": snapshot.to_dict().get("name", "Rota")}
            for snapshot in snapshots
        ]
    }


def set_active(db, uid, data, claims):
    """Desativação revoga operações no próximo envio; motorista mantém check-out."""
    fleet = owner(db, uid, claims)
    data = _only_keys(data, {"driverId", "active"})
    identifier = text(data, "driverId")
    if "/" in identifier or type(data.get("active")) is not bool:
        raise RouteError("invalid-argument", "invalid_account", "Dados inválidos.")
    reference = db.collection("drivers").document(identifier)
    driver = reference.get().to_dict() or {}
    if driver.get("fleet_owner_id") != fleet:
        raise RouteError(
            "permission-denied",
            "driver_other_fleet",
            "Motorista não pertence à sua frota.",
        )
    reference.update({"active": data["active"]})
    return {"success": True}
