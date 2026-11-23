"""Uso manual no Emulator Suite (somente dados fictícios, somente emuladores).

  python scripts/seed_and_call.py seed
  python scripts/seed_and_call.py checkin motorista1@example.test TAG-BUS-01
  python scripts/seed_and_call.py show TAG-BUS-01
  python scripts/seed_and_call.py claims motorista1@example.test
  python scripts/seed_and_call.py set-role motorista1@example.test passageiro

A ROLE OFICIAL é a custom claim `role` do Firebase Auth (definida aqui com o
Admin SDK, só no Auth Emulator, ANTES de qualquer token ser emitido). O campo
`users/{uid}.role` do Firestore é apenas informativo/legado: alterá-lo não
concede nem remove permissão.

Requer os emuladores firestore, auth e functions rodando (veja CHECKIN_GUIDE.md).
"""
import base64
import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emulator_auth import emulator_admin_app  # noqa: E402  (também ajusta o sys.path)
from roles import ALLOWED_ROLES, set_user_role  # noqa: E402

PROJECT = "demo-checkin"
AUTH = os.environ.get("AUTH_URL", "http://127.0.0.1:9099")
FUNCS = os.environ.get("FUNCTIONS_URL", "http://127.0.0.1:5001")
PASSWORD = "senha-ficticia-123"
os.environ.setdefault("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")


def _db():
    from google.auth.credentials import AnonymousCredentials
    from google.cloud import firestore
    return firestore.Client(project=PROJECT, credentials=AnonymousCredentials())


def _auth(path, email):
    return requests.post(
        f"{AUTH}/identitytoolkit.googleapis.com/v1/accounts:{path}?key=fake",
        json={"email": email, "password": PASSWORD, "returnSecureToken": True},
        timeout=10)


def auth_user(email):
    """Cria (ou reaproveita) o usuário no Auth Emulator; devolve (uid, idToken)."""
    r = _auth("signUp", email)
    if r.status_code != 200:
        r = _auth("signInWithPassword", email)
    r.raise_for_status()
    j = r.json()
    return j["localId"], j["idToken"]


def _admin():
    return emulator_admin_app(PROJECT)


def _set_role(uid, role):
    """Claim `role` via Admin SDK (preserva outras claims; idempotente)."""
    return set_user_role(uid, role, app=_admin())


def _token_payload(id_token):
    """Payload do JWT (sem verificar assinatura; uso local, só para exibir)."""
    part = id_token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def seed():
    db = _db()
    owner, _ = auth_user("dono@example.test")
    owner2, _ = auth_user("dono2@example.test")
    # Claims ANTES de qualquer token usado depois (checkin() faz novo login).
    _set_role(owner, "dono_frota")
    _set_role(owner2, "dono_frota")
    users = {
        "motorista1@example.test": ("motorista", owner, True),
        "motorista2@example.test": ("motorista", owner, True),
        "inativo@example.test": ("motorista", owner, False),
        "outrafrota@example.test": ("motorista", owner2, True),
        "semcadastro@example.test": ("motorista", owner, None),
        "passageiro@example.test": ("passageiro", None, None),
    }
    # `role` no Firestore = espelho INFORMATIVO/legado; a autorização usa a claim.
    db.collection("users").document(owner).set(
        {"name": "Dono Fictício", "email": "dono@example.test",
         "role": "dono_frota", "fleet_owner_id": owner})            # Acrescentar no dicionário: {"cpf": "618.619.885-90", "photo_user": "foto.png"}
    for i, (email, (role, fleet, active)) in enumerate(users.items(), 1):
        uid, _ = auth_user(email)
        _set_role(uid, role)
        data = {"name": email.split("@")[0], "email": email, "role": role}
        if fleet:
            data["fleet_owner_id"] = fleet
        db.collection("users").document(uid).set(data)
        if active is not None:
            db.collection("drivers").document(f"drv{i}").set(
                {"user_id": uid, "fleet_owner_id": fleet,
                 "driver_code": f"DRV{i:03d}", "active": active})
    db.collection("buses").document("bus1").set(
        {"tag_code": "TAG-BUS-01", "plate": "HPX-9876",
         "model": "Marcopolo Torino", "capacity": 45,
         "fleet_owner_id": owner, "active_driver_id": None})
    db.collection("buses").document("bus2").set(
        {"tag_code": "TAG-BUS-02", "plate": "ABC-1234", "model": "Mercedes O500",
         "capacity": 50, "fleet_owner_id": owner2, "active_driver_id": None})
    print("Seed ok. Usuários (senha %s): %s" % (PASSWORD, ", ".join(users)))
    print("Claims 'role' definidas no Auth Emulator (verifique: claims <email>).")


def checkin(email, tag):
    _, token = auth_user(email)
    r = requests.post(f"{FUNCS}/{PROJECT}/us-central1/checkIn",
                      json={"data": {"tagCode": tag}},
                      headers={"Authorization": f"Bearer {token}"}, timeout=30)
    print(r.status_code, r.text)


def claims(email):
    """Mostra as claims gravadas no Auth e a role presente em um token NOVO."""
    from firebase_admin import auth
    user = auth.get_user_by_email(email, app=_admin())
    print("custom_claims no Auth :", user.custom_claims)
    _, token = auth_user(email)  # novo login = token com as claims atuais
    print("role no token novo    :", _token_payload(token).get("role"))


def set_role(email, role):
    """Altera a claim. Tokens JÁ emitidos continuam com a role antiga."""
    if role not in ALLOWED_ROLES:
        sys.exit("role inválida. Permitidas: " + ", ".join(ALLOWED_ROLES))
    from firebase_admin import auth
    user = auth.get_user_by_email(email, app=_admin())
    r = _set_role(user.uid, role)
    print("role: %s -> %s (faça novo login para o token refletir)"
          % (r["previous_role"], r["role"]))


def show(tag):
    for d in _db().collection("buses").where("tag_code", "==", tag).stream():
        print(d.id, d.to_dict())


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["help"]
    {"seed": lambda: seed(), "checkin": lambda: checkin(*args),
     "show": lambda: show(*args), "claims": lambda: claims(*args),
     "set-role": lambda: set_role(*args)}.get(cmd, lambda: print(__doc__))()
