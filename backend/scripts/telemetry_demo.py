r"""Simulador manual da telemetria no emulador (dados fictícios, projeto demo-*).

    py scripts\telemetry_demo.py seed                 # cria motorista+ônibus fictícios
    py scripts\telemetry_demo.py fresh                # envia telemetria RECENTE (valida de verdade)
    py scripts\telemetry_demo.py old --age 60         # grava telemetria ANTIGA (60 s) como se o celular tivesse sumido
    py scripts\telemetry_demo.py show                 # mostra /telemetry
    py scripts\telemetry_demo.py end --bus bus3       # fim de viagem (remove o nó); usa o motorista em check-in
    py scripts\telemetry_demo.py end --bus bus3 --auth-token $idToken   # idem, via callable endTelemetry

`fresh` passa pelo mesmo caminho do callable `sendTelemetry` (autorização no
Firestore + validação + carimbo de updated_at do servidor); por isso, depois de
`old` + monitor, rodar `fresh` demonstra a RECUPERAÇÃO da conexão.

`end` segue a mesma ideia do `fresh`:
  * com --auth-token: chama o callable `endTelemetry` no Functions Emulator
    (o token precisa ser do motorista em check-in naquele ônibus);
  * sem token: lê `buses/{bus}.active_driver_id` no Firestore e executa a mesma
    lógica do callable como esse motorista (autorização completa, sem $idToken).
    Se o ônibus não tem motorista ativo (viagem já encerrada), remove o nó
    direto, como o monitor faria.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emulator_rtdb  # noqa: E402
import telemetry  # noqa: E402

DRIVER = "demo_driver"
FLEET = "demo_fleet"
CLAIMS = {"role": "motorista"}


# MOSTRAR LISTA DE ONIBUS DO FIRESTORE:

def list_buses(db, root):
    """Lista os ônibus do Firestore e mostra a telemetria correspondente."""
    docs = db.collection("buses").stream()

    found = False

    for doc in docs:
        found = True
        bus_id = doc.id
        data = doc.to_dict() or {}
        telemetry_data = root.child(bus_id).get()

        print(f"\nID: {bus_id}")
        print(f"Placa: {data.get('plate', 'Não informada')}")
        print(f"Modelo: {data.get('model', 'Não informado')}")
        print(f"Motorista ativo: {data.get('active_driver_id')}")
        print(f"Dono da frota: {data.get('fleet_owner_id')}")

        if telemetry_data is None:
            print("Telemetria: SEM DADOS")
        else:
            print("Telemetria:")
            print(json.dumps(
                telemetry_data,
                indent=2,
                ensure_ascii=False,
                sort_keys=True
            ))

    if not found:
        print("Nenhum ônibus encontrado na coleção buses.")



import urllib.error
import urllib.request


def send_telemetry_authenticated(bus_id, lat, lng, status, auth_token, project,
                                 speed=32.5, distance=None):

    """Chama sendTelemetry pelo Functions Emulator usando um ID token."""
    url = (
        f"http://127.0.0.1:5001/{project}/southamerica-east1/sendTelemetry"
    )

    payload = {
        "data": {
            "busId": bus_id,
            "lat": lat,
            "lng": lng,
            "speed": speed,
            "heading": 180,
            "status": status,
        }
    }
    if distance is not None:
        payload["data"]["distance"] = distance

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detalhe = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"sendTelemetry retornou HTTP {err.code}: {detalhe}"
        ) from err
    except urllib.error.URLError as err:
        raise RuntimeError(
            f"Não foi possível acessar o Functions Emulator: {err}"
        ) from err


def end_telemetry_authenticated(bus_id, auth_token, project):
    """Chama endTelemetry pelo Functions Emulator usando um ID token."""
    url = f"http://127.0.0.1:5001/{project}/southamerica-east1/endTelemetry"
    request = urllib.request.Request(
        url,
        data=json.dumps({"data": {"busId": bus_id}}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detalhe = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"endTelemetry retornou HTTP {err.code}: {detalhe}"
        ) from err
    except urllib.error.URLError as err:
        raise RuntimeError(
            f"Não foi possível acessar o Functions Emulator: {err}"
        ) from err


def end_telemetry_as_active_driver(db, root, bus_id):
    """Encerra a telemetria SEM token: age como o motorista em check-in no ônibus.

    Passa pela mesma lógica do callable (`handle_end_telemetry`), então a
    autorização é real: motorista ativo, cadastro ativo e mesma frota.
    Devolve (resultado, código_de_saída).
    """
    bus_doc = db.collection("buses").document(bus_id).get()
    if not bus_doc.exists:
        print(f"Ônibus '{bus_id}' não encontrado no Firestore.")
        return None, 1

    active_driver = (bus_doc.to_dict() or {}).get("active_driver_id")
    if not isinstance(active_driver, str) or not active_driver.strip():
        # Sem motorista ativo = viagem já encerrada: ninguém tem autorização
        # para chamar endTelemetry; o monitor removeria o nó de qualquer forma.
        existed = root.child(bus_id).get() is not None
        root.child(bus_id).delete()
        print(f"'{bus_id}' não tem motorista ativo (viagem já encerrada); "
              "nó de telemetria removido diretamente.")
        return {"success": True, "busId": bus_id, "removed": existed}, 0

    try:
        out = telemetry.handle_end_telemetry(
            db, root, active_driver, {"busId": bus_id}, CLAIMS)
    except telemetry.TelemetryError as err:
        print(f"Recusado ({err.code} / {err.reason}): {err}")
        return None, 1
    return out, 0



# FUNÇÃO MAIN

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])  # Inicialização dos dados de telemetria
    ap.add_argument("cmd", choices=["seed", "fresh", "old", "show", "end", "buses"])
    ap.add_argument("--project", default=os.environ.get("GCLOUD_PROJECT", "loirinha-1a25f"))
    ap.add_argument("--bus", default=None)
    ap.add_argument(
        "--auth-token",
        default=None,
        help="Token Firebase ID para testar com autenticação real"
    )
    ap.add_argument("--age", type=float, default=60, help="idade em segundos (cmd old)")
    ap.add_argument("--lat", type=float, default=-3.6667)
    ap.add_argument("--lng", type=float, default=-45.3800)
    ap.add_argument("--status", default="in_service")
    ap.add_argument("--speed", type=float, default=32.5, help="km/h (cmd fresh/old)")
    ap.add_argument("--distance", type=float, default=None,
                    help="distancia HIPOTETICA em km (cmd fresh/old); opcional")
    a = ap.parse_args(argv)
    bus_id = a.bus or "bus_01"

    root = emulator_rtdb.emulator_telemetry_root(a.project)
    db = emulator_rtdb.emulator_firestore_client(a.project)

    if a.cmd == "seed":
        db.collection("users").document(DRIVER).set(
            {"name": "Motorista Ficticio", "role": "motorista", "fleet_owner_id": FLEET})
        db.collection("drivers").document(DRIVER).set(
            {"user_id": DRIVER, "fleet_owner_id": FLEET, "driver_code": "DRV-DEMO", "active": True})
        db.collection("buses").document(a.bus).set(
            {"tag_code": f"TAG-{a.bus}", "plate": "HPX-9876", "capacity": 45,
             "fleet_owner_id": FLEET, "active_driver_id": DRIVER})
        print(f"OK: motorista {DRIVER} em check-in no onibus {a.bus}")

    elif a.cmd == "fresh":
        if a.auth_token:
            out = send_telemetry_authenticated(
                bus_id=bus_id,
                lat=a.lat,
                lng=a.lng,
                status=a.status,
                auth_token=a.auth_token,
                project=a.project,
                speed=a.speed,
                distance=a.distance,
            )
        else:
            body = {
                "busId": bus_id,
                "lat": a.lat,
                "lng": a.lng,
                "speed": a.speed,
                "heading": 180,
                "status": a.status,
            }
            if a.distance is not None:
                body["distance"] = a.distance
            out = telemetry.handle_send_telemetry(db, root, DRIVER, body, CLAIMS)

        print(json.dumps(out, indent=2, ensure_ascii=False))

    elif a.cmd == "old":
        t = telemetry.now_ms() - int(a.age * 1000)
        node = {
            "lat": a.lat, "lng": a.lng, "speed": round(a.speed), "heading": 180,
            "status": a.status, "updated_at": t, "captured_at": t,
            "is_online": True, "connection_status": "online"}
        if a.distance is not None:
            node["distance"] = a.distance
        root.child(a.bus).set(node)
        print(f"OK: {a.bus} gravado com updated_at {a.age:g}s atras (ainda 'online'); "
              "o monitor deve marcar connection_lost em ate ~5 s")
    elif a.cmd == "end":
        if a.auth_token:
            try:
                out = end_telemetry_authenticated(
                    bus_id=bus_id,
                    auth_token=a.auth_token,
                    project=a.project,
                )
            except RuntimeError as err:
                print(err)
                return 1
        else:
            out, code = end_telemetry_as_active_driver(db, root, bus_id)
            if out is None:
                return code

        print(json.dumps(out, indent=2, ensure_ascii=False))

    elif a.cmd == "show":
        if a.bus:
            bus_doc = db.collection("buses").document(a.bus).get()

            if not bus_doc.exists:
                print(f"Ônibus '{a.bus}' não encontrado no Firestore.")
                return 1

            data = root.child(a.bus).get()

            if data is None:
                print(f"Ônibus '{a.bus}' cadastrado, mas sem telemetria.")
            else:
                print(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            print(json.dumps(root.get(), indent=2, ensure_ascii=False, sort_keys=True))

    elif a.cmd == "buses":
        list_buses(db, root)


if __name__ == "__main__":
    raise SystemExit(main())
