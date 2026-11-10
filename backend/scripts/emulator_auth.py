"""Admin SDK apontado SOMENTE para o Firebase Auth Emulator.

Sem FIREBASE_AUTH_EMULATOR_HOST o Admin SDK falaria com o Auth de PRODUÇÃO;
por isso este módulo recusa qualquer configuração que não seja:
  - host local (127.0.0.1 / localhost / ::1), e
  - projeto "demo-*" ou "loirinha-1a25f" (o host local é a trava que importa).
Nenhuma credencial é lida, gravada ou necessária.
"""
from __future__ import annotations

import os
import sys

_FUNCTIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "functions")
if _FUNCTIONS_DIR not in sys.path:
    sys.path.insert(0, _FUNCTIONS_DIR)

DEFAULT_AUTH_HOST = "127.0.0.1:9099"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
APP_NAME = "emulator-claims"


ALLOWED_PROJECT = "loirinha-1a25f"  # projeto real; só é usado contra EMULADORES locais


class EmulatorGuardError(Exception):
    pass


def is_allowed_project(project_id: str) -> bool:
    return project_id.startswith("demo-") or project_id == ALLOWED_PROJECT


def _host_name(host: str) -> str:
    return host.strip().rpartition(":")[0].strip("[]")


def emulator_admin_app(project_id: str):
    """Devolve um firebase_admin.App ligado ao Auth Emulator (cria 1x)."""
    if not is_allowed_project(project_id):
        raise EmulatorGuardError(
            f"Recusado: projeto {project_id!r} não é 'demo-*' nem 'loirinha-1a25f'.")
    host = (os.environ.get("FIREBASE_AUTH_EMULATOR_HOST")
            or DEFAULT_AUTH_HOST).strip()
    if _host_name(host) not in LOOPBACK_HOSTS:
        raise EmulatorGuardError(
            f"Recusado: FIREBASE_AUTH_EMULATOR_HOST={host!r} não é local.")
    # Precisa estar definido ANTES de qualquer chamada ao Admin SDK.
    os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = host

    import firebase_admin
    try:
        return firebase_admin.get_app(APP_NAME)
    except ValueError:
        return firebase_admin.initialize_app(
            options={"projectId": project_id}, name=APP_NAME)
