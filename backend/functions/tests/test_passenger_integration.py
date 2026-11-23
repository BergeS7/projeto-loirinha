"""Integração real da projeção com Firestore/RTDB locais, sem chamadas de produção."""

import pytest
from conftest import make_bus, make_driver, MOTORISTA
from rtdb_support import telemetry_root, db_available, SKIP_REASON
from telemetry import handle_send_telemetry
from passenger import validate_catalog, catalog_document

pytestmark = pytest.mark.skipif(not db_available(), reason=SKIP_REASON)


def test_gps_publicado_inclui_eta_sem_identidade_privada(db):
    """O mesmo heartbeat abastece o passageiro com campos derivados e sanitizados."""
    make_driver(db, "m1")
    make_bus(db, "bus1", active="m1")
    catalog = validate_catalog(
        {
            "lines": [
                {
                    "id": "l1",
                    "numero": "101",
                    "nome": "Linha teste",
                    "cor": "#123456",
                    "pontoIds": ["p1", "p2"],
                    "operacao": "06–20",
                    "intervalo": "20 min",
                    "tracado": [[-3.6, -45.31], [-3.6, -45.30]],
                    "circular": False,
                }
            ],
            "stops": [
                {
                    "id": "p1",
                    "nome": "Início",
                    "referencia": "Rua A",
                    "lat": -3.6,
                    "lng": -45.31,
                },
                {
                    "id": "p2",
                    "nome": "Fim",
                    "referencia": "Rua B",
                    "lat": -3.6,
                    "lng": -45.30,
                },
            ],
            "buses": [
                {"id": "bus1", "linhaId": "l1", "prefixo": "001", "sentido": "Fim"}
            ],
            "notices": [],
        }
    )
    for group, collection in (("lines", "public_lines"), ("buses", "public_buses")):
        for item in catalog[group]:
            db.collection(collection).document(item["id"]).set(catalog_document(item))
    root = telemetry_root()
    root.delete()
    handle_send_telemetry(
        db,
        root,
        "m1",
        {
            "busId": "bus1",
            "lat": -3.6,
            "lng": -45.305,
            "speed": 36,
            "heading": 90,
            "status": "in_service",
        },
        MOTORISTA,
        server_now=1_800_000_000_000,
    )
    node = root.child("bus1").get()
    assert node["linhaId"] == "l1"
    assert node["progresso"] == pytest.approx(0.5, abs=0.001)
    assert node["proximoPontoId"] == "p2"
    assert node["previsoes"]["p2"] == 1
    assert node["lotacao"] == "desconhecida"
    assert not {"active_driver_id", "fleet_owner_id", "user_id"} & node.keys()
