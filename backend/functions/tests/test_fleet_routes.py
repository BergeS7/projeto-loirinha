"""Testes de rotas por frota e de `drivers.id_route` (functions/fleet_routes.py).

Os testes de lógica e de regras rodam no Firestore Emulator, só com dados
fictícios. Os de ponta a ponta (Auth + Functions) só rodam com CHECKIN_E2E=1,
como test_e2e_callable.py.
"""
import copy
import os

import pytest
import requests
from firebase_admin import auth

import fleet_routes as fr
import seed_routes as sr
from conftest import (DONO_FROTA, FLEET_A, FLEET_B, MOTORISTA, PASSAGEIRO,
                      PROJECT, make_bus, make_driver_record, make_user)
from test_rules import Client
from test_seed_routes import CASOS_INVALIDOS, valid_route

DRV_A1, DRV_A2, DRV_B1 = "drvA1", "drvA2", "drvB1"
UID_A1, UID_A2, UID_B1 = "mot_a1", "mot_a2", "mot_b1"


# ------------------------------------------------------------------ helpers --
def route_body():
    return copy.deepcopy(sr.ROUTES["route001"])


def make_route(db, route_id, fleet, name=None):
    """Rota com fleet_owner_id (None = rota legada, sem frota)."""
    data = route_body()
    if name:
        data["name"] = name
    if fleet is not None:
        data["fleet_owner_id"] = fleet
    db.collection("routes").document(route_id).set(data)
    return route_id


def driver_doc(db, doc_id):
    return db.collection("drivers").document(doc_id).get().to_dict()


def err(fn, *args):
    with pytest.raises(fr.RouteError) as exc:
        fn(*args)
    return exc.value


@pytest.fixture
def world(db):
    """Duas frotas (A e B), dois motoristas na A, um na B, um ônibus em cada."""
    make_user(db, FLEET_A, "dono_frota", FLEET_A)
    make_user(db, FLEET_B, "dono_frota", FLEET_B)
    for uid, fleet, doc in ((UID_A1, FLEET_A, DRV_A1), (UID_A2, FLEET_A, DRV_A2),
                            (UID_B1, FLEET_B, DRV_B1)):
        make_user(db, uid, "motorista", fleet)
        make_driver_record(db, uid, fleet, doc_id=doc)
    make_bus(db, "busA", "TAG-A", FLEET_A)
    make_bus(db, "busB", "TAG-B", FLEET_B)
    return db


# ======================================================== validação (paridade) =
def test_validador_concorda_com_o_do_seed():
    assert fr.validate_route_data(route_body()) == []
    assert fr.validate_route_data(sr.ROUTES["route002"]) == []
    for nome, mutacao, _ in CASOS_INVALIDOS:
        r = valid_route()
        mutacao(r)
        assert fr.validate_route_data(r) != [], f"{nome}: deveria ser inválido"
    assert fr.validate_route_data(["x"]) != []


# ================================================================ createRoute ==
def test_dono_cadastra_rota_na_propria_frota(world):
    out = fr.handle_create_route(world, FLEET_A, route_body(), DONO_FROTA)
    assert out["success"] is True
    saved = world.collection("routes").document(out["routeId"]).get().to_dict()
    assert saved == {**route_body(), "fleet_owner_id": FLEET_A}


def test_cada_cadastro_gera_documento_novo(world):
    a = fr.handle_create_route(world, FLEET_A, route_body(), DONO_FROTA)["routeId"]
    b = fr.handle_create_route(world, FLEET_A, route_body(), DONO_FROTA)["routeId"]
    assert a != b
    assert len(list(world.collection("routes").stream())) == 2


def test_dono_nao_cadastra_rota_em_outra_frota(world):
    body = {**route_body(), "fleet_owner_id": FLEET_B}  # tentativa de forjar a frota
    e = err(fr.handle_create_route, world, FLEET_A, body, DONO_FROTA)
    assert e.reason == "unexpected_field" and e.code == "invalid-argument"
    assert list(world.collection("routes").stream()) == []


def test_frota_da_rota_vem_do_usuario_autenticado(world):
    out = fr.handle_create_route(world, FLEET_B, route_body(), DONO_FROTA)
    saved = world.collection("routes").document(out["routeId"]).get().to_dict()
    assert saved["fleet_owner_id"] == FLEET_B


@pytest.mark.parametrize("nome,mutacao,_", CASOS_INVALIDOS[:12],
                         ids=[c[0] for c in CASOS_INVALIDOS[:12]])
def test_rota_invalida_nao_e_gravada(world, nome, mutacao, _):
    body = valid_route()
    mutacao(body)
    e = err(fr.handle_create_route, world, FLEET_A, body, DONO_FROTA)
    assert e.reason in {"invalid_route", "unexpected_field"}
    assert list(world.collection("routes").stream()) == []


@pytest.mark.parametrize("payload", [None, [], "texto", 5])
def test_payload_que_nao_e_objeto(world, payload):
    e = err(fr.handle_create_route, world, FLEET_A, payload, DONO_FROTA)
    assert e.reason == "invalid_payload"


def test_usuario_que_nao_e_dono_da_propria_frota_nao_cadastra(world):
    make_user(world, "dono_x", "dono_frota", FLEET_A)  # fleet_owner_id != uid
    e = err(fr.handle_create_route, world, "dono_x", route_body(), DONO_FROTA)
    assert e.reason == "fleet_not_owned"
    e = err(fr.handle_create_route, world, "sem_cadastro", route_body(), DONO_FROTA)
    assert e.reason == "user_not_found"
    assert list(world.collection("routes").stream()) == []


# ============================================================ autenticação/role ==
CHAMADAS = [
    ("create", fr.handle_create_route, "dono", lambda: route_body()),
    ("set", fr.handle_set_driver_route, "dono",
     lambda: {"driverId": DRV_A1, "routeId": "r"}),
    ("bus", fr.handle_get_bus_route, "dono", lambda: {"busId": "busA"}),
    ("my", fr.handle_get_my_route, "mot", lambda: None),
]


@pytest.mark.parametrize("nome,fn,quem,payload", CHAMADAS, ids=[c[0] for c in CHAMADAS])
def test_sem_autenticacao(world, nome, fn, quem, payload):
    claims = DONO_FROTA if quem == "dono" else MOTORISTA
    for uid in (None, ""):
        e = err(fn, world, uid, payload(), claims)
        assert (e.code, e.reason) == ("unauthenticated", "unauthenticated")


@pytest.mark.parametrize("nome,fn,quem,payload", CHAMADAS, ids=[c[0] for c in CHAMADAS])
def test_claim_ausente_invalida_ou_errada(world, nome, fn, quem, payload):
    uid = FLEET_A if quem == "dono" else UID_A1
    outra = MOTORISTA if quem == "dono" else DONO_FROTA
    esperado = "not_a_fleet_owner" if quem == "dono" else "not_a_driver"
    assert err(fn, world, uid, payload(), None).reason == "missing_role_claim"
    assert err(fn, world, uid, payload(), {}).reason == "missing_role_claim"
    assert err(fn, world, uid, payload(), {"role": "admin"}).reason == "invalid_role"
    assert err(fn, world, uid, payload(), {"role": ""}).reason == "invalid_role"
    assert err(fn, world, uid, payload(), PASSAGEIRO).reason == esperado
    e = err(fn, world, uid, payload(), outra)
    assert (e.code, e.reason) == ("permission-denied", esperado)


def test_role_legada_no_firestore_nao_autoriza(world):
    # users/{uid}.role diz dono_frota, mas a claim do token diz motorista.
    make_user(world, UID_A1, role="dono_frota", fleet=FLEET_A)
    e = err(fr.handle_create_route, world, UID_A1, route_body(), MOTORISTA)
    assert e.reason == "not_a_fleet_owner"
    assert list(world.collection("routes").stream()) == []


# ============================================================ setDriverRoute ==
def assign(db, uid, driver_id, route_id, claims=DONO_FROTA):
    return fr.handle_set_driver_route(
        db, uid, {"driverId": driver_id, "routeId": route_id}, claims)


def test_dono_atribui_rota_a_motorista_da_propria_frota(world):
    make_route(world, "rA", FLEET_A)
    before = driver_doc(world, DRV_A1)
    out = assign(world, FLEET_A, DRV_A1, "rA")
    assert out["success"] is True and out["routeId"] == "rA"
    assert driver_doc(world, DRV_A1) == {**before, "id_route": "rA"}
    assert "id_route" not in driver_doc(world, DRV_A2)  # outro motorista intacto


def test_atribuicao_rejeitada_rota_inexistente(world):
    e = err(assign, world, FLEET_A, DRV_A1, "nao_existe")
    assert (e.code, e.reason) == ("not-found", "route_not_found")
    assert "id_route" not in driver_doc(world, DRV_A1)
    assert list(world.collection("routes").stream()) == []  # nada foi criado


def test_atribuicao_rejeitada_rota_de_outra_frota(world):
    make_route(world, "rB", FLEET_B)
    e = err(assign, world, FLEET_A, DRV_A1, "rB")
    assert (e.code, e.reason) == ("permission-denied", "route_other_fleet")
    assert "id_route" not in driver_doc(world, DRV_A1)


def test_atribuicao_rejeitada_rota_sem_frota(world):
    make_route(world, "legada", None)
    e = err(assign, world, FLEET_A, DRV_A1, "legada")
    assert e.reason == "route_without_fleet"
    assert "id_route" not in driver_doc(world, DRV_A1)


def test_dono_nao_altera_rota_de_motorista_de_outra_frota(world):
    make_route(world, "rA", FLEET_A)
    make_route(world, "rB", FLEET_B)
    world.collection("drivers").document(DRV_B1).update({"id_route": "rB"})
    for route in ("rA", "rB"):
        e = err(assign, world, FLEET_A, DRV_B1, route)
        assert (e.code, e.reason) == ("permission-denied", "driver_other_fleet")
    assert driver_doc(world, DRV_B1)["id_route"] == "rB"


def test_atribuicao_motorista_inexistente(world):
    make_route(world, "rA", FLEET_A)
    e = err(assign, world, FLEET_A, "drv_fantasma", "rA")
    assert (e.code, e.reason) == ("not-found", "driver_not_found")
    assert not world.collection("drivers").document("drv_fantasma").get().exists


@pytest.mark.parametrize("payload,reason", [
    ({"routeId": "rA"}, "invalid_driver_id"),
    ({"driverId": DRV_A1}, "invalid_route_id"),
    ({"driverId": "", "routeId": "rA"}, "invalid_driver_id"),
    ({"driverId": DRV_A1, "routeId": "a/b"}, "invalid_route_id"),
    ({"driverId": 5, "routeId": "rA"}, "invalid_driver_id"),
    ({"driverId": DRV_A1, "routeId": "rA", "fleet_owner_id": FLEET_B},
     "unexpected_field"),
    ({"driverId": DRV_A1, "routeId": "rA", "id_route": "x"}, "unexpected_field"),
    ("texto", "invalid_payload"),
])
def test_atribuicao_payload_invalido(world, payload, reason):
    make_route(world, "rA", FLEET_A)
    e = err(fr.handle_set_driver_route, world, FLEET_A, payload, DONO_FROTA)
    assert e.code == "invalid-argument" and e.reason == reason
    assert "id_route" not in driver_doc(world, DRV_A1)


def test_motorista_nao_atribui_nem_altera_a_propria_rota(world):
    make_route(world, "rA", FLEET_A)
    make_route(world, "rA2", FLEET_A)
    assign(world, FLEET_A, DRV_A1, "rA")
    # atribuir a outro motorista
    assert err(assign, world, UID_A1, DRV_A2, "rA", MOTORISTA).reason == "not_a_fleet_owner"
    # alterar a própria rota
    assert err(assign, world, UID_A1, DRV_A1, "rA2", MOTORISTA).reason == "not_a_fleet_owner"
    assert driver_doc(world, DRV_A1)["id_route"] == "rA"
    assert "id_route" not in driver_doc(world, DRV_A2)


def test_motorista_nao_cadastra_rota(world):
    e = err(fr.handle_create_route, world, UID_A1, route_body(), MOTORISTA)
    assert (e.code, e.reason) == ("permission-denied", "not_a_fleet_owner")
    assert list(world.collection("routes").stream()) == []


# ================================================================ getBusRoute ==
def bus_route(db, uid, bus_id, claims=DONO_FROTA):
    return fr.handle_get_bus_route(db, uid, {"busId": bus_id}, claims)


def checkin_simulado(db, bus_id, uid):
    db.collection("buses").document(bus_id).update({"active_driver_id": uid})


def test_dono_consulta_rota_do_onibus_com_motorista(world):
    make_route(world, "rA", FLEET_A, name="Linha A")
    assign(world, FLEET_A, DRV_A1, "rA")
    checkin_simulado(world, "busA", UID_A1)
    out = bus_route(world, FLEET_A, "busA")
    assert out["success"] is True and out["busId"] == "busA"
    assert out["driverDocId"] == DRV_A1
    assert out["route"]["routeId"] == "rA" and out["route"]["name"] == "Linha A"
    assert "fleet_owner_id" not in out["route"]


def test_consulta_rota_do_onibus_outra_frota(world):
    make_route(world, "rB", FLEET_B)
    assign(world, FLEET_B, DRV_B1, "rB")
    checkin_simulado(world, "busB", UID_B1)
    e = err(bus_route, world, FLEET_A, "busB")
    assert (e.code, e.reason) == ("permission-denied", "bus_other_fleet")


def test_consulta_sem_motorista_ativo(world):
    e = err(bus_route, world, FLEET_A, "busA")
    assert (e.code, e.reason) == ("failed-precondition", "no_active_driver")


def test_consulta_motorista_sem_rota(world):
    checkin_simulado(world, "busA", UID_A1)
    assert err(bus_route, world, FLEET_A, "busA").reason == "driver_without_route"


def test_consulta_onibus_inexistente(world):
    assert err(bus_route, world, FLEET_A, "busX").reason == "bus_not_found"


def test_consulta_nao_vaza_rota_de_outra_frota_gravada_no_motorista(world):
    make_route(world, "rB", FLEET_B)
    world.collection("drivers").document(DRV_A1).update({"id_route": "rB"})  # dado adulterado
    checkin_simulado(world, "busA", UID_A1)
    assert err(bus_route, world, FLEET_A, "busA").reason == "route_other_fleet"


def test_consulta_rota_removida(world):
    world.collection("drivers").document(DRV_A1).update({"id_route": "sumiu"})
    checkin_simulado(world, "busA", UID_A1)
    assert err(bus_route, world, FLEET_A, "busA").reason == "route_not_found"


def test_consulta_motorista_do_onibus_de_outra_frota(world):
    # ônibus da A ocupado por motorista cadastrado na B (dado inconsistente)
    checkin_simulado(world, "busA", UID_B1)
    assert err(bus_route, world, FLEET_A, "busA").reason == "driver_other_fleet"


def test_motorista_nao_consulta_rota_de_onibus(world):
    checkin_simulado(world, "busA", UID_A1)
    assert err(bus_route, world, UID_A1, "busA", MOTORISTA).reason == "not_a_fleet_owner"


@pytest.mark.parametrize("payload,reason", [
    ({}, "invalid_bus_id"), ({"busId": "a/b"}, "invalid_bus_id"),
    ({"busId": "busA", "fleet_owner_id": FLEET_B}, "unexpected_field"),
])
def test_consulta_payload_invalido(world, payload, reason):
    e = err(fr.handle_get_bus_route, world, FLEET_A, payload, DONO_FROTA)
    assert e.reason == reason


# ================================================================= getMyRoute ==
def my_route(db, uid, data=None, claims=MOTORISTA):
    return fr.handle_get_my_route(db, uid, data, claims)


def test_motorista_ve_a_propria_rota(world):
    make_route(world, "rA", FLEET_A, name="Linha 1")
    make_route(world, "rA2", FLEET_A, name="Linha 2")
    assign(world, FLEET_A, DRV_A1, "rA")
    assign(world, FLEET_A, DRV_A2, "rA2")
    out = my_route(world, UID_A1)
    assert out["route"]["routeId"] == "rA" and out["route"]["name"] == "Linha 1"
    assert out["driverDocId"] == DRV_A1
    assert my_route(world, UID_A2, {})["route"]["routeId"] == "rA2"


@pytest.mark.parametrize("payload", [
    {"driverId": DRV_A2}, {"routeId": "rA2"}, {"user_id": UID_A2},
    {"id_route": "rA2"}, {"uid": UID_A2},
])
def test_motorista_nao_consulta_rota_alheia_por_parametro(world, payload):
    make_route(world, "rA", FLEET_A)
    make_route(world, "rA2", FLEET_A)
    assign(world, FLEET_A, DRV_A1, "rA")
    assign(world, FLEET_A, DRV_A2, "rA2")
    e = err(my_route, world, UID_A1, payload)
    assert (e.code, e.reason) == ("invalid-argument", "unexpected_field")


def test_payload_que_nao_e_objeto_na_rota_propria(world):
    assert err(my_route, world, UID_A1, ["x"]).reason == "invalid_payload"


def test_motorista_sem_rota_atribuida(world):
    e = err(my_route, world, UID_A1)
    assert (e.code, e.reason) == ("failed-precondition", "driver_without_route")


def test_motorista_sem_cadastro_ou_inativo(world):
    make_user(world, "sem_cad", "motorista", FLEET_A)
    assert err(my_route, world, "sem_cad").reason == "driver_record_not_found"
    assert err(my_route, world, "sem_usuario").reason == "user_not_found"
    world.collection("drivers").document(DRV_A1).update({"active": False})
    assert err(my_route, world, UID_A1).reason == "driver_inactive"


def test_motorista_nao_ve_rota_de_outra_frota_nem_sem_frota(world):
    make_route(world, "rB", FLEET_B)
    make_route(world, "legada", None)
    for route in ("rB", "legada"):
        world.collection("drivers").document(DRV_A1).update({"id_route": route})
        assert err(my_route, world, UID_A1).reason in {
            "route_other_fleet", "route_without_fleet"}


def test_frota_do_motorista_diverge_da_do_usuario(world):
    make_route(world, "rA", FLEET_A)
    world.collection("drivers").document(DRV_A1).update({"id_route": "rA"})
    make_user(world, UID_A1, "motorista", FLEET_B)
    assert err(my_route, world, UID_A1).reason == "fleet_mismatch_driver_user"


def test_dono_e_passageiro_nao_usam_get_my_route(world):
    assert err(my_route, world, FLEET_A, None, DONO_FROTA).reason == "not_a_driver"
    assert err(my_route, world, UID_A1, None, PASSAGEIRO).reason == "not_a_driver"


# ======================================================== find_fleet_route_id ==
def test_find_fleet_route_id(world):
    assert fr.find_fleet_route_id(world, FLEET_A) is None  # nada cadastrado
    make_route(world, "rB", FLEET_B)
    make_route(world, "legada", None)
    assert fr.find_fleet_route_id(world, FLEET_A) is None  # só alheia e legada
    make_route(world, "r2", FLEET_A)
    make_route(world, "r1", FLEET_A)
    assert fr.find_fleet_route_id(world, FLEET_A) == "r1"        # menor ID
    assert fr.find_fleet_route_id(world, FLEET_A, "r2") == "r2"  # mantém válida
    assert fr.find_fleet_route_id(world, FLEET_A, "rB") == "r1"  # ignora alheia
    assert fr.find_fleet_route_id(world, FLEET_A, "legada") == "r1"
    assert fr.find_fleet_route_id(world, FLEET_A, "fantasma") == "r1"
    assert fr.find_fleet_route_id(world, FLEET_B) == "rB"
    assert fr.find_fleet_route_id(world, None) is None
    assert fr.find_fleet_route_id(world, "") is None


# ========================================================= regras do Firestore ==
def test_regras_rota_legada_e_publica_para_autenticados(world, emulator_host):
    make_route(world, "legada", None)
    assert Client(emulator_host, UID_A1, "motorista").get("routes/legada").status_code == 200
    assert Client(emulator_host, None).get("routes/legada").status_code == 403


def test_regras_rota_da_frota_so_para_o_dono(world, emulator_host):
    make_route(world, "rA", FLEET_A)
    path = "routes/rA"
    assert Client(emulator_host, FLEET_A, "dono_frota").get(path).status_code == 200
    assert Client(emulator_host, FLEET_A).get(path).status_code == 403          # sem claim
    assert Client(emulator_host, FLEET_B, "dono_frota").get(path).status_code == 403
    assert Client(emulator_host, UID_A1, "motorista").get(path).status_code == 403
    assert Client(emulator_host, UID_A2, "motorista").get(path).status_code == 403
    assert Client(emulator_host, "p1", "passageiro").get(path).status_code == 403
    assert Client(emulator_host, None).get(path).status_code == 403


def test_regras_clientes_nao_escrevem_em_rotas_nem_em_id_route(world, emulator_host):
    make_route(world, "rA", FLEET_A)
    before = driver_doc(world, DRV_A1)
    for uid, role in ((FLEET_A, "dono_frota"), (UID_A1, "motorista")):
        c = Client(emulator_host, uid, role)
        assert c.patch("routes/rA", {"name": "x"}).status_code == 403
        assert c.patch("routes/nova", {"name": "x"}).status_code == 403
        assert c.delete("routes/rA").status_code == 403
        assert c.patch(f"drivers/{DRV_A1}", {"id_route": "rA"}).status_code == 403
    assert driver_doc(world, DRV_A1) == before
    assert world.collection("routes").document("nova").get().exists is False


# ==================================================== ponta a ponta (opcional) ==
AUTH_URL = os.environ.get("AUTH_URL", "http://127.0.0.1:9099")
FUNCS = os.environ.get("FUNCTIONS_URL", "http://127.0.0.1:5001")
PASSWORD = "senha-ficticia-123"
e2e = pytest.mark.skipif(os.environ.get("CHECKIN_E2E") != "1",
                         reason="defina CHECKIN_E2E=1 (emuladores completos)")


def _db():
    from google.auth.credentials import AnonymousCredentials
    from google.cloud import firestore
    return firestore.Client(project=PROJECT, credentials=AnonymousCredentials())


def _app():
    from emulator_auth import emulator_admin_app
    return emulator_admin_app(PROJECT)


def _new_user(email, role):
    from roles import set_user_role
    uid = auth.create_user(email=email, password=PASSWORD, app=_app()).uid
    set_user_role(uid, role, app=_app())
    return uid


def _token(email):
    r = requests.post(
        f"{AUTH_URL}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake",
        json={"email": email, "password": PASSWORD, "returnSecureToken": True}, timeout=10)
    r.raise_for_status()
    return r.json()["idToken"]


def _call(name, token, data):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.post(f"{FUNCS}/{PROJECT}/southamerica-east1/{name}",
                         json={"data": data}, headers=h, timeout=30)


def _reason(r):
    return r.json()["error"]["details"]["reason"]


@pytest.fixture
def clean_auth():
    host = os.environ["FIREBASE_AUTH_EMULATOR_HOST"]
    requests.delete(f"http://{host}/emulator/v1/projects/{PROJECT}/accounts",
                    timeout=10).raise_for_status()
    yield


@e2e
@pytest.mark.parametrize("name", ["createRoute", "setDriverRoute", "getBusRoute",
                                  "getMyRoute"])
def test_e2e_sem_token_401(name):
    r = _call(name, None, {})
    assert r.status_code == 401 and r.json()["error"]["status"] == "UNAUTHENTICATED"


@e2e
def test_e2e_fluxo_dono_e_motorista(clean_auth):
    db = _db()
    dono = _new_user("dono@e2e.test", "dono_frota")
    mot = _new_user("mot@e2e.test", "motorista")
    make_user(db, dono, "dono_frota", dono)
    make_user(db, mot, "motorista", dono)
    make_driver_record(db, mot, dono, doc_id="drvE2E")
    make_bus(db, "busE2E", "TAG-E2E", dono)
    t_dono, t_mot = _token("dono@e2e.test"), _token("mot@e2e.test")

    r = _call("createRoute", t_dono, route_body())
    assert r.status_code == 200
    route_id = r.json()["result"]["routeId"]
    assert db.collection("routes").document(route_id).get().to_dict()[
        "fleet_owner_id"] == dono

    r = _call("setDriverRoute", t_dono, {"driverId": "drvE2E", "routeId": route_id})
    assert r.status_code == 200
    assert driver_doc(db, "drvE2E")["id_route"] == route_id

    r = _call("getMyRoute", t_mot, {})
    assert r.status_code == 200 and r.json()["result"]["route"]["routeId"] == route_id
    r = _call("getMyRoute", t_mot, {"driverId": "outro"})
    assert r.status_code == 400 and _reason(r) == "unexpected_field"

    assert _call("checkIn", t_mot, {"tagCode": "TAG-E2E"}).status_code == 200
    r = _call("getBusRoute", t_dono, {"busId": "busE2E"})
    assert r.status_code == 200 and r.json()["result"]["route"]["routeId"] == route_id

    r = _call("createRoute", t_mot, route_body())
    assert r.status_code == 403 and _reason(r) == "not_a_fleet_owner"
    r = _call("setDriverRoute", t_mot, {"driverId": "drvE2E", "routeId": route_id})
    assert r.status_code == 403 and _reason(r) == "not_a_fleet_owner"
    r = _call("getMyRoute", t_dono, {})
    assert r.status_code == 403 and _reason(r) == "not_a_driver"


@e2e
def test_e2e_seed_grava_id_route_somente_com_rota_valida(clean_auth):
    import seed_and_call as seed
    db = _db()
    seed.seed()  # 1ª vez: ainda não há rota de frota -> nenhum id_route
    assert all("id_route" not in d.to_dict() for d in db.collection("drivers").stream())

    owner = auth.get_user_by_email("dono@example.test", app=_app()).uid
    route_id = fr.handle_create_route(db, owner, route_body(), DONO_FROTA)["routeId"]
    seed.seed()  # 2ª vez: motoristas da frota do dono recebem a rota real
    docs = {d.id: d.to_dict() for d in db.collection("drivers").stream()}
    for doc_id in ("drv1", "drv2", "drv3"):
        assert docs[doc_id]["id_route"] == route_id
    assert "id_route" not in docs["drv4"]  # outra frota: sem rota própria
    seed.seed()  # idempotente: mantém a rota já válida
    assert driver_doc(db, "drv1")["id_route"] == route_id
