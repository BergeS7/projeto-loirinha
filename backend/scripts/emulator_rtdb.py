"""Admin SDK apontado SOMENTE para os emuladores Realtime Database e Firestore.

Mesmas travas de `emulator_auth.py`: recusa projeto que não seja "demo-*"/"loirinha-1a25f" e
host que não seja local (127.0.0.1 / localhost / ::1). Nenhuma credencial é
lida, gravada ou necessária; sem o host do emulador o Admin SDK falaria com
PRODUÇÃO, por isso a variável é sempre definida aqui, antes de qualquer chamada.
"""
from __future__ import annotations

import os
import sys

_FUNCTIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "functions")
if _FUNCTIONS_DIR not in sys.path:
    sys.path.insert(0, _FUNCTIONS_DIR)

DEFAULT_DB_HOST = "127.0.0.1:9000"
DEFAULT_FIRESTORE_HOST = "127.0.0.1:8080"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
APP_NAME = "emulator-rtdb"


ALLOWED_PROJECT = "loirinha-1a25f"  # projeto real; só é usado contra EMULADORES locais


class EmulatorGuardError(Exception):
    pass


def is_allowed_project(project_id: str) -> bool:
    return project_id.startswith("demo-") or project_id == ALLOWED_PROJECT

def database_namespace(project_id: str) -> str:
    """Namespace usado pelo Realtime Database Emulator neste projeto."""
    if not is_allowed_project(project_id):
        raise EmulatorGuardError(
            f"Recusado: projeto {project_id!r} não é 'demo-*' nem 'loirinha-1a25f'."
        )
    if project_id.startswith("demo-"):
        return project_id
    # Projeto real: a instância padrão do RTDB se chama <projeto>-default-rtdb
    # (mesmo nome usado em .firebaserc e em functions/main.py).
    return f"{project_id}-default-rtdb"

def _host_name(host: str) -> str:
    return host.strip().rpartition(":")[0].strip("[]")


def _guarded_host(project_id: str, env_var: str, default: str) -> str:
    if not is_allowed_project(project_id):
        raise EmulatorGuardError(
            f"Recusado: projeto {project_id!r} não é 'demo-*' nem 'loirinha-1a25f'.")
    host = (os.environ.get(env_var) or default).strip()
    if _host_name(host) not in LOOPBACK_HOSTS:
        raise EmulatorGuardError(f"Recusado: {env_var}={host!r} não é local.")
    os.environ[env_var] = host
    return host


def emulator_telemetry_root(project_id: str):
    """Referência Admin SDK de /telemetry no Realtime Database Emulator."""
    _guarded_host(project_id, "FIREBASE_DATABASE_EMULATOR_HOST", DEFAULT_DB_HOST)
    import firebase_admin
    from firebase_admin import db

    try:
        app = firebase_admin.get_app(APP_NAME)
    except ValueError:
        app = firebase_admin.initialize_app(
            options={"projectId": project_id,
                     "databaseURL": f"https://{database_namespace(project_id)}.firebaseio.com"},
            name=APP_NAME)
    return db.reference("/telemetry", app=app)


def emulator_firestore_client(project_id: str):
    """Cliente Firestore ligado ao Firestore Emulator (credencial anônima)."""
    _guarded_host(project_id, "FIRESTORE_EMULATOR_HOST", DEFAULT_FIRESTORE_HOST)
    from google.auth.credentials import AnonymousCredentials
    from google.cloud import firestore

    return firestore.Client(project=project_id, credentials=AnonymousCredentials())
