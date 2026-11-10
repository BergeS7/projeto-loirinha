"""Regras do Realtime Database (database.rules.json) via REST do emulador.

Token = JWT sem assinatura (o emulador aceita); sem token = anônimo.
Se as regras NÃO estiverem carregadas o emulador fica aberto e estes testes
falham (o que é desejado): negar escrita anônima só acontece com regras ativas.
"""
import pytest

from rtdb_support import SKIP_REASON, db_available, jwt, rest, telemetry_root

pytestmark = pytest.mark.skipif(not db_available(), reason=SKIP_REASON)

SEED = {"lat": -3.6, "lng": -45.3, "speed": 10, "heading": 1,
        "status": "in_service", "updated_at": 1_800_000_000_000,
        "captured_at": 1_800_000_000_000,
        "is_online": True, "connection_status": "online"}

ACTORS = {
    "anonimo": None,
    "passageiro": jwt("p1", "passageiro"),
    "motorista_do_onibus": jwt("m1", "motorista"),
    "dono_frota": jwt("o1", "dono_frota"),
    "sem_role": jwt("x1"),
}


@pytest.fixture
def root():
    r = telemetry_root()
    r.delete()
    r.child("bus_01").set(SEED)  # Admin SDK ignora regras (seed)
    r.parent.child("segredo").set("x")
    return r


def test_anonimo_nao_le_telemetria(root):
    assert rest("GET", "telemetry").status_code == 401
    assert rest("GET", "telemetry/bus_01").status_code == 401


@pytest.mark.parametrize("actor", ["passageiro", "motorista_do_onibus", "dono_frota", "sem_role"])
def test_autenticado_le_telemetria(root, actor):
    r = rest("GET", "telemetry/bus_01", token=ACTORS[actor])
    assert r.status_code == 200 and r.json() == SEED
    assert rest("GET", "telemetry", token=ACTORS[actor]).status_code == 200


def test_autenticado_nao_le_fora_de_telemetry(root):
    assert rest("GET", "segredo", token=ACTORS["passageiro"]).status_code == 401
    assert rest("GET", "", token=ACTORS["passageiro"]).status_code == 401


@pytest.mark.parametrize("actor", list(ACTORS))
@pytest.mark.parametrize("method,path,body", [
    ("PUT", "telemetry/bus_01", {**SEED, "lat": 1}),
    ("PUT", "telemetry/bus_novo", SEED),
    ("PATCH", "telemetry/bus_01", {"is_online": True}),
    ("PATCH", "telemetry/bus_01", {"connection_status": "online",
                                   "updated_at": 9_999_999_999_999}),
    ("PUT", "telemetry/bus_01/is_online", True),
    ("DELETE", "telemetry/bus_01", None),
    ("PUT", "outro_no", 1),
], ids=["put_no", "put_novo", "patch_is_online", "patch_conexao_e_hora",
        "put_campo", "delete", "put_fora_de_telemetry"])
def test_nenhum_cliente_escreve(root, actor, method, path, body):
    r = rest(method, path, token=ACTORS[actor], body=body)
    assert r.status_code == 401, r.text
    assert root.child("bus_01").get() == SEED  # dados intactos
    assert root.parent.child("outro_no").get() is None
