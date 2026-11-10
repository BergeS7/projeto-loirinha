"""Apoio dos testes de telemetria: Realtime Database Emulator.

Os testes de telemetria só rodam com o RTDB Emulator ligado
(`FIREBASE_DATABASE_EMULATOR_HOST`, definido por `firebase emulators:exec`);
sem ele são PULADOS (skip visível), para não quebrar quem roda a suíte antiga
apenas com `--only firestore`.
"""
import base64
import json
import os
import time

import requests

from conftest import PROJECT
import emulator_rtdb

DB_HOST_ENV = "FIREBASE_DATABASE_EMULATOR_HOST"
NS = emulator_rtdb.database_namespace(PROJECT)
SUBPROCESS_OK = True  # pode executar scripts/telemetry_monitor.py de verdade

SKIP_REASON = ("Realtime Database Emulator não está ligado. Rode "
               "`.\\scripts\\test-telemetry.ps1`.")


def db_available() -> bool:
    return bool(os.environ.get(DB_HOST_ENV))


def telemetry_root():
    """Referência Admin SDK (acesso total) de /telemetry no emulador."""
    return emulator_rtdb.emulator_telemetry_root(PROJECT)


# --------------------------------------------------------------- REST + regras
def _b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


def jwt(uid, role=None):
    """JWT SEM assinatura no formato que o emulador espera (mesmos campos que
    `@firebase/rules-unit-testing` gera); `role` vira custom claim."""
    now = int(time.time())
    payload = {
        "iat": now, "auth_time": now, "exp": now + 3600,
        "aud": PROJECT, "iss": f"https://securetoken.google.com/{PROJECT}",
        "sub": uid, "user_id": uid, "uid": uid,
        "firebase": {"identities": {}, "sign_in_provider": "custom"},
    }
    if role is not None:
        payload["role"] = role
    return f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(payload)}."


def rest(method, path, token=None, body=None):
    """Requisição REST ao emulador, avaliada pelas regras (token=None: anônimo).
    O token vai no header Authorization e também em ?auth=."""
    url = f"http://{os.environ[DB_HOST_ENV]}/{path.strip('/')}.json"
    params = {"ns": NS}
    headers = {}
    if token:
        params["auth"] = token
        headers["Authorization"] = f"Bearer {token}"
    return requests.request(method, url, params=params, headers=headers,
                            json=body, timeout=10)
