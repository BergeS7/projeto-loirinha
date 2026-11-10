"""scripts/distance_decay.py contra o Realtime Database Emulator.

Rode com:  firebase emulators:exec --only "firestore,database" --project loirinha-1a25f
           "<python> -m pytest functions/tests/test_distance_decay.py -v"
"""
import pytest

import distance_decay as dd
import telemetry
from rtdb_support import SKIP_REASON, db_available, telemetry_root

pytestmark = pytest.mark.skipif(not db_available(), reason=SKIP_REASON)

NOW = 1_800_000_000_000


def lost(distance=10.0, speed=60, **over):
    n = {"lat": -3.6, "lng": -45.3, "speed": speed, "heading": 1,
         "status": "in_service", "updated_at": NOW, "captured_at": NOW,
         "is_online": False, "connection_status": "connection_lost"}
    if distance is not None:
        n["distance"] = distance
    n.update(over)
    return n


@pytest.fixture
def root():
    r = telemetry_root()
    r.delete()
    return r


def test_reduz_distance_pela_velocidade_em_30s(root):
    root.child("b1").set(lost(10.0, 60))  # 60 km/h * 30 s = 0,5 km
    res = dd.tick(root, 30, now_ms=NOW + 99)
    assert res.adjusted == [("b1", 9.5)] and res.errors == []
    n = root.child("b1").get()
    assert n["distance"] == 9.5 and n["distance_adjusted_at"] == NOW + 99
    # nada mais mudou
    for k in ("updated_at", "captured_at", "is_online", "connection_status", "speed", "lat"):
        assert n[k] == lost()[k]


def test_ciclos_sucessivos_e_piso_em_zero(root):
    root.child("b1").set(lost(1.0, 60))
    dd.tick(root, 30)
    dd.tick(root, 30)
    assert root.child("b1").get()["distance"] == 0
    assert dd.tick(root, 30).adjusted == []  # já em 0: nada a fazer
    assert root.child("b1").get()["distance"] == 0


@pytest.mark.parametrize("node", [
    lost(10, 60, connection_status="online", is_online=True),  # online
    lost(10, 0),                    # parado
    lost(10, -5), lost(10, "60"), lost(10, None),
    lost(None),                     # sem distance
    lost(-1), lost("10"), lost(float("nan")),
], ids=["online", "speed0", "speed_neg", "speed_txt", "speed_none",
        "sem_distance", "distance_neg", "distance_txt", "distance_nan"])
def test_nao_mexe_quando_nao_deve(root, node):
    root.child("b1").set(node)
    assert dd.tick(root, 30).adjusted == []
    assert root.child("b1").get() == node


def test_varios_onibus_so_os_perdidos(root):
    root.child("a").set(lost(5, 36))
    root.child("b").set(lost(5, 36, connection_status="online", is_online=True))
    dd.tick(root, 30)
    assert root.child("a").get()["distance"] == 4.7
    assert root.child("b").get()["distance"] == 5


def test_telemetria_nova_interrompe_o_ajuste(root):
    root.child("b1").set(lost(10, 60))
    dd.tick(root, 30)
    # chega telemetria nova: nó volta a online com a distance enviada
    root.child("b1").set({**lost(7.0, 40), "is_online": True,
                          "connection_status": "online", "updated_at": NOW + 40_000})
    before = root.child("b1").get()
    assert dd.tick(root, 30).adjusted == []
    assert root.child("b1").get() == before


def test_telemetria_chega_entre_leitura_e_escrita(root):
    """CAS: a escrita do ajuste é descartada e o nó novo (online) prevalece."""
    root.child("b1").set(lost(10, 60))
    fresh = {**lost(7.0, 40), "is_online": True, "connection_status": "online",
             "updated_at": NOW + 40_000}
    ref = root.child("b1")
    cls = ref.__class__
    real = cls.set_if_unchanged
    fired = []

    def racing(self, etag, value):
        if not fired:
            fired.append(1)
            self.set(fresh)  # chegada concorrente antes do 1º CAS
        return real(self, etag, value)

    cls.set_if_unchanged = racing
    try:
        assert dd.adjust_node(root, "b1", 30, NOW + 50_000) == "skipped"
    finally:
        cls.set_if_unchanged = real
    assert root.child("b1").get() == fresh


def test_no_inexistente(root):
    assert dd.adjust_node(root, "nada", 30, NOW) == "gone"


def test_distance_enviada_na_telemetria_e_validada(root):
    # (usa só a validação; autorização é coberta em test_telemetry.py)
    base = {"busId": "b1", "lat": -3.6, "lng": -45.3, "speed": 30,
            "heading": 1, "status": "in_service"}
    assert telemetry.parse_payload({**base, "distance": 2.5})["distance"] == 2.5
    assert telemetry.parse_payload(base)["distance"] is None
    for bad in (-1, "2", float("nan"), float("inf"), True, 20_001):
        with pytest.raises(telemetry.TelemetryError) as ei:
            telemetry.parse_payload({**base, "distance": bad})
        assert ei.value.reason == "invalid_distance"
