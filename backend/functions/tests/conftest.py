"""Fixtures dos testes. Usam EXCLUSIVAMENTE o Firestore Emulator e dados fictícios.

Trava de segurança: a sessão aborta se FIRESTORE_EMULATOR_HOST não estiver
definido ou se o projeto não for "demo-*" nem "loirinha-1a25f".
"""
import os
import sys

import pytest
import requests
from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts"))

PROJECT = os.environ.get("GCLOUD_PROJECT", "loirinha-1a25f")
FLEET_A = "usr_df001"
FLEET_B = "usr_df002"

# Claims de token usadas pelos testes de lógica (a role OFICIAL é a claim).
MOTORISTA = {"role": "motorista"}
PASSAGEIRO = {"role": "passageiro"}
DONO_FROTA = {"role": "dono_frota"}


def pytest_sessionstart(session):
    host = os.environ.get("FIRESTORE_EMULATOR_HOST")
    if not host:
        pytest.exit(
            "FIRESTORE_EMULATOR_HOST não definido. Rode via "
            "`firebase emulators:exec` (veja CHECKIN_GUIDE.md). "
            "Recusando rodar para evitar tocar em produção.",
            returncode=2,
        )
    if not (PROJECT.startswith("demo-") or PROJECT == "loirinha-1a25f"):
        pytest.exit(f"Projeto '{PROJECT}' não é 'demo-*' nem 'loirinha-1a25f'.", returncode=2)


@pytest.fixture(scope="session")
def emulator_host():
    return os.environ["FIRESTORE_EMULATOR_HOST"]


@pytest.fixture(scope="session")
def db():
    return firestore.Client(project=PROJECT, credentials=AnonymousCredentials())


@pytest.fixture(autouse=True)
def clean_firestore(emulator_host):
    url = (f"http://{emulator_host}/emulator/v1/projects/{PROJECT}"
           "/databases/(default)/documents")
    requests.delete(url, timeout=10).raise_for_status()
    yield


# ---------------------------------------------------------------- seed helpers
def make_user(db, uid, role="motorista", fleet=FLEET_A, name=None):
    """`role` aqui é só o espelho INFORMATIVO/legado em users/{uid}; a role que
    autoriza é a custom claim do token (veja MOTORISTA/PASSAGEIRO/DONO_FROTA)."""
    data = {"name": name or f"Fictício {uid}", "email": f"{uid}@example.test",
            "role": role}
    if fleet is not None:
        data["fleet_owner_id"] = fleet
    db.collection("users").document(uid).set(data)
    return uid


def make_driver_record(db, user_id, fleet=FLEET_A, active=True, doc_id=None,
                       code="DRV001"):
    ref = db.collection("drivers").document(doc_id) if doc_id \
        else db.collection("drivers").document()
    ref.set({"user_id": user_id, "fleet_owner_id": fleet,
             "driver_code": code, "active": active})
    return ref.id


def make_driver(db, uid, fleet=FLEET_A, active=True):
    """Usuário motorista + cadastro em drivers, consistentes."""
    make_user(db, uid, "motorista", fleet)
    make_driver_record(db, uid, fleet, active)
    return uid


def make_bus(db, bus_id="bus1", tag="TAG-BUS-01", fleet=FLEET_A, active=None):
    db.collection("buses").document(bus_id).set({
        "tag_code": tag, "plate": "HPX-9876", "model": "Marcopolo Torino",
        "capacity": 45, "fleet_owner_id": fleet, "active_driver_id": active,
    })
    return bus_id


def bus_state(db, bus_id="bus1"):
    return db.collection("buses").document(bus_id).get().to_dict()
