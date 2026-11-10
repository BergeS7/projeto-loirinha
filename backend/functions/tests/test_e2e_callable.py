"""E2E opcional: chama a Cloud Function `checkIn` pelo Functions Emulator
usando tokens reais do Auth Emulator, COM custom claims `role`.

Só roda com CHECKIN_E2E=1 e emuladores firestore+auth+functions ativos
(veja CHECKIN_GUIDE.md). Fluxo de cada usuário:
  1) cria o usuário no Auth Emulator (Admin SDK)
  2) define a claim `role` (Admin SDK, merge que preserva outras claims)
  3) SÓ ENTÃO faz login (signInWithPassword) -> o ID token já contém a claim
"""
import base64
import json
import os

import pytest
import requests
from firebase_admin import auth

from conftest import PROJECT, bus_state, make_bus, make_driver, make_user
from emulator_auth import emulator_admin_app
from roles import set_user_role

pytestmark = pytest.mark.skipif(os.environ.get("CHECKIN_E2E") != "1",
                                reason="defina CHECKIN_E2E=1 (emuladores completos)")

AUTH = os.environ.get("AUTH_URL", "http://127.0.0.1:9099")
FUNCS = os.environ.get("FUNCTIONS_URL", "http://127.0.0.1:5001")
URL = f"{FUNCS}/{PROJECT}/southamerica-east1/checkIn"
PASSWORD = "senha-ficticia-123"


@pytest.fixture(scope="module")
def app():
    return emulator_admin_app(PROJECT)


@pytest.fixture(autouse=True)
def clean_auth(app):
    """Zera os usuários do Auth EMULATOR antes de cada teste E2E."""
    host = os.environ["FIREBASE_AUTH_EMULATOR_HOST"]
    requests.delete(f"http://{host}/emulator/v1/projects/{PROJECT}/accounts",
                    timeout=10).raise_for_status()
    yield


def new_user(app, email, role=None, raw_claims=None):
    """Cria usuário e define claims ANTES de qualquer login. Devolve uid.

    role      -> via set_user_role (valida e preserva outras claims)
    raw_claims-> grava claims arbitrárias (para simular role inválida/ausente)
    """
    uid = auth.create_user(email=email, password=PASSWORD, app=app).uid
    if raw_claims is not None:
        auth.set_custom_user_claims(uid, raw_claims, app=app)
    if role is not None:
        set_user_role(uid, role, app=app)
    return uid


def sign_in(email):
    r = requests.post(
        f"{AUTH}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake",
        json={"email": email, "password": PASSWORD, "returnSecureToken": True},
        timeout=10)
    r.raise_for_status()
    return r.json()["idToken"]


def payload(token):
    part = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def call(token, data):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.post(URL, json={"data": data}, headers=h, timeout=30)


def db_():
    from google.auth.credentials import AnonymousCredentials
    from google.cloud import firestore
    return firestore.Client(project=PROJECT, credentials=AnonymousCredentials())


def reason(r):
    return r.json()["error"]["details"]["reason"]


# ---------------------------------------------------------------- válidos ---
def test_e2e_valido_motorista_com_claim(app):
    uid = new_user(app, "e2e1@example.test", "motorista")
    make_driver(db_(), uid)
    make_bus(db_())
    tok = sign_in("e2e1@example.test")
    assert payload(tok)["role"] == "motorista"  # o token reflete a claim
    r = call(tok, {"tagCode": "TAG-BUS-01", "uid": "ignorado", "role": "dono_frota"})
    assert r.status_code == 200 and r.json()["result"]["success"] is True
    assert bus_state(db_())["active_driver_id"] == uid


def test_e2e_valido_mesmo_com_role_legada_diferente_no_firestore(app):
    uid = new_user(app, "e2e1b@example.test", "motorista")
    make_user(db_(), uid, role="passageiro")  # espelho legado diverge
    from conftest import make_driver_record
    make_driver_record(db_(), uid)
    make_bus(db_())
    r = call(sign_in("e2e1b@example.test"), {"tagCode": "TAG-BUS-01"})
    assert r.status_code == 200 and r.json()["result"]["success"] is True


# ------------------------------------------------------------- recusados ---
def test_e2e_sem_token():
    make_bus(db_())
    r = call(None, {"tagCode": "TAG-BUS-01"})
    assert r.status_code == 401
    assert r.json()["error"]["status"] == "UNAUTHENTICATED"
    assert bus_state(db_())["active_driver_id"] is None


def test_e2e_passageiro(app):
    uid = new_user(app, "e2e2@example.test", "passageiro")
    make_user(db_(), uid, role="passageiro", fleet=None)
    make_bus(db_())
    r = call(sign_in("e2e2@example.test"), {"tagCode": "TAG-BUS-01"})
    assert r.status_code == 403 and reason(r) == "not_a_driver"
    assert bus_state(db_())["active_driver_id"] is None


def test_e2e_dono_frota(app):
    uid = new_user(app, "e2e3@example.test", "dono_frota")
    make_user(db_(), uid, role="dono_frota", fleet=uid)
    make_bus(db_(), fleet=uid)
    r = call(sign_in("e2e3@example.test"), {"tagCode": "TAG-BUS-01"})
    assert r.status_code == 403 and reason(r) == "not_a_driver"
    assert bus_state(db_())["active_driver_id"] is None


def test_e2e_sem_claim_role(app):
    uid = new_user(app, "e2e4@example.test")  # nenhuma claim
    make_driver(db_(), uid)  # Firestore diz motorista; o token não tem role
    make_bus(db_())
    tok = sign_in("e2e4@example.test")
    assert "role" not in payload(tok)
    r = call(tok, {"tagCode": "TAG-BUS-01"})
    assert r.status_code == 403 and reason(r) == "missing_role_claim"
    assert bus_state(db_())["active_driver_id"] is None


@pytest.mark.parametrize("n,bad", [(1, "admin"), (2, "MOTORISTA"), (3, "")])
def test_e2e_role_invalida(app, n, bad):
    email = f"e2e5-{n}@example.test"
    uid = new_user(app, email, raw_claims={"role": bad})
    make_driver(db_(), uid)
    make_bus(db_())
    r = call(sign_in(email), {"tagCode": "TAG-BUS-01"})
    assert r.status_code == 403 and reason(r) == "invalid_role"
    assert bus_state(db_())["active_driver_id"] is None


# ------------------------------------------------ token antigo/desatualizado ---
def test_e2e_token_antigo_nao_reflete_promocao_ate_novo_login(app):
    """Usuário vira motorista DEPOIS de obter o token: o token antigo continua
    sem permissão; um novo login (token novo) passa a ter."""
    uid = new_user(app, "e2e6@example.test", "passageiro")
    make_driver(db_(), uid)
    make_bus(db_())
    old = sign_in("e2e6@example.test")
    assert payload(old)["role"] == "passageiro"

    set_user_role(uid, "motorista", app=app)  # promoção no Auth

    r_old = call(old, {"tagCode": "TAG-BUS-01"})  # token desatualizado
    assert r_old.status_code == 403 and reason(r_old) == "not_a_driver"
    assert bus_state(db_())["active_driver_id"] is None

    new = sign_in("e2e6@example.test")  # novo login = claims atuais
    assert payload(new)["role"] == "motorista"
    r_new = call(new, {"tagCode": "TAG-BUS-01"})
    assert r_new.status_code == 200 and r_new.json()["result"]["success"] is True
    assert bus_state(db_())["active_driver_id"] == uid


def test_e2e_set_user_role_preserva_outras_claims(app):
    uid = new_user(app, "e2e7@example.test", raw_claims={"beta": True, "plano": "x"})
    r = set_user_role(uid, "motorista", app=app)
    assert r["previous_role"] is None
    r = set_user_role(uid, "passageiro", app=app)
    assert r["previous_role"] == "motorista"
    claims = auth.get_user(uid, app=app).custom_claims
    assert claims == {"beta": True, "plano": "x", "role": "passageiro"}
    # e o token novo carrega todas
    p = payload(sign_in("e2e7@example.test"))
    assert p["role"] == "passageiro" and p["beta"] is True and p["plano"] == "x"


# ------------------------------------------------------------------ seed ---
def _import_seed():
    import seed_and_call
    return seed_and_call


def test_e2e_seed_define_claims_e_e_idempotente(app):
    seed = _import_seed()
    esperado = {
        "dono@example.test": "dono_frota", "dono2@example.test": "dono_frota",
        "motorista1@example.test": "motorista", "motorista2@example.test": "motorista",
        "inativo@example.test": "motorista", "outrafrota@example.test": "motorista",
        "semcadastro@example.test": "motorista",
        "passageiro@example.test": "passageiro",
    }

    def snapshot():
        d = db_()
        return {c: sorted(x.id for x in d.collection(c).stream())
                for c in ("users", "drivers", "buses")}

    seed.seed()
    primeira = snapshot()
    for email, role in esperado.items():
        assert auth.get_user_by_email(email, app=app).custom_claims == {"role": role}
        assert payload(sign_in(email))["role"] == role

    # claim extra (ex.: beta) não pode ser apagada por um novo seed
    uid = auth.get_user_by_email("motorista1@example.test", app=app).uid
    auth.set_custom_user_claims(uid, {"role": "passageiro", "beta": True}, app=app)
    seed.seed()  # segunda execução
    assert snapshot() == primeira, "seed duplicou/alterou documentos"
    c = auth.get_user_by_email("motorista1@example.test", app=app).custom_claims
    assert c == {"role": "motorista", "beta": True}
    assert len(auth.list_users(app=app).users) == len(esperado)  # sem usuários duplicados


def test_e2e_seed_permite_checkin_valido_e_recusas(app):
    seed = _import_seed()
    seed.seed()
    t1 = sign_in("motorista1@example.test")
    r = call(t1, {"tagCode": "TAG-BUS-01"})
    assert r.status_code == 200 and r.json()["result"]["success"] is True
    # passageiro do seed, ônibus livre da outra frota: recusado pela role
    r = call(sign_in("passageiro@example.test"), {"tagCode": "TAG-BUS-02"})
    assert r.status_code == 403 and reason(r) == "not_a_driver"
    # motorista da outra frota no ônibus da frota A (já ocupado): a checagem de
    # frota vem antes da de ocupação
    r = call(sign_in("outrafrota@example.test"), {"tagCode": "TAG-BUS-01"})
    assert r.status_code == 403 and reason(r) == "bus_other_fleet"
