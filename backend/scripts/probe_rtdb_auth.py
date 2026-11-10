r"""Diagnóstico: qual forma de token o RTDB Emulator aceita? (emuladores ligados)

    .\functions\venv\Scripts\python.exe scripts\probe_rtdb_auth.py

Grava um nó fictício em /telemetry/probe e lê com cada variante de token.
Esperado com as regras carregadas: anônimo=401; token válido=200.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emulator_rtdb  # noqa: E402

PROJECT = os.environ.get("GCLOUD_PROJECT", "loirinha-1a25f")
root = emulator_rtdb.emulator_telemetry_root(PROJECT)
host = os.environ["FIREBASE_DATABASE_EMULATOR_HOST"]
ns = emulator_rtdb.database_namespace(PROJECT)
root.child("probe").set({"ok": True})


def b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


now = int(time.time())
mini = {"uid": "u1", "user_id": "u1", "sub": "u1"}
full = {**mini, "iat": now, "auth_time": now, "exp": now + 3600, "aud": PROJECT,
        "iss": f"https://securetoken.google.com/{PROJECT}",
        "firebase": {"identities": {}, "sign_in_provider": "custom"}}
hdr = {"alg": "none", "typ": "JWT"}
tok = {"minimo": f"{b64(hdr)}.{b64(mini)}.", "completo": f"{b64(hdr)}.{b64(full)}."}

url = f"http://{host}/telemetry/probe.json"
cases = [("anonimo", {}, {}), ("Bearer owner (admin)", {}, {"Authorization": "Bearer owner"})]
for name, t in tok.items():
    cases += [(f"?auth= {name}", {"auth": t}, {}),
              (f"?access_token= {name}", {"access_token": t}, {}),
              (f"header Bearer {name}", {}, {"Authorization": f"Bearer {t}"})]
for label, params, headers in cases:
    r = requests.get(url, params={"ns": ns, **params}, headers=headers, timeout=10)
    print(f"{r.status_code}  {label:32} {r.text[:60]}")
root.child("probe").delete()
