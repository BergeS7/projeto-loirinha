"""Testes das Firestore Security Rules via REST do emulador.

Requisições com `Authorization: Bearer <JWT sem assinatura>` são avaliadas pelas
regras (o emulador aceita tokens não assinados); sem o header, o usuário é
anônimo. Se as regras NÃO estiverem carregadas o emulador fica aberto e estes
testes falham (o que é desejado).
"""
import base64
import json

import requests

from conftest import FLEET_A, PROJECT, bus_state, make_bus, make_driver, make_user


def _b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


def _headers(uid, role=None):
    """JWT sem assinatura; `role` vira a custom claim (request.auth.token.role)."""
    if uid is None:
        return {}
    payload = {"user_id": uid, "sub": uid}
    if role is not None:
        payload["role"] = role
    tok = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(payload)}."
    return {"Authorization": f"Bearer {tok}"}


class Client:
    def __init__(self, host, uid, role=None):
        self.base = (f"http://{host}/v1/projects/{PROJECT}"
                     "/databases/(default)/documents")
        self.h = _headers(uid, role)

    def get(self, path):
        return requests.get(f"{self.base}/{path}", headers=self.h, timeout=10)

    def patch(self, path, fields):
        body = {"fields": {k: {"stringValue": v} for k, v in fields.items()}}
        mask = "&".join(f"updateMask.fieldPaths={k}" for k in fields)
        return requests.patch(f"{self.base}/{path}?{mask}", json=body,
                              headers=self.h, timeout=10)

    def delete(self, path):
        return requests.delete(f"{self.base}/{path}", headers=self.h, timeout=10)


def seed(db):
    make_driver(db, "m1")
    make_driver(db, "m2")
    make_user(db, "p1", role="passageiro", fleet=None)
    make_bus(db)


def test_anonimo_nao_le_onibus(db, emulator_host):
    seed(db)
    assert Client(emulator_host, None).get("buses/bus1").status_code == 403


def test_autenticado_le_onibus(db, emulator_host):
    seed(db)
    assert Client(emulator_host, "p1").get("buses/bus1").status_code == 200


def test_motorista_nao_assume_onibus_direto(db, emulator_host):
    seed(db)
    before = bus_state(db)
    r = Client(emulator_host, "m1").patch("buses/bus1", {"active_driver_id": "m1"})
    assert r.status_code == 403
    assert bus_state(db) == before


def test_dono_da_frota_tambem_nao_escreve_active_driver_id(db, emulator_host):
    seed(db)
    make_user(db, FLEET_A, role="dono_frota", fleet=FLEET_A)
    before = bus_state(db)
    r = Client(emulator_host, FLEET_A).patch("buses/bus1", {"active_driver_id": "m1"})
    assert r.status_code == 403
    assert bus_state(db) == before


def test_cliente_nao_cria_nem_apaga_onibus(db, emulator_host):
    seed(db)
    c = Client(emulator_host, "m1")
    assert c.patch("buses/novo", {"tag_code": "X"}).status_code == 403
    assert c.delete("buses/bus1").status_code == 403
    assert bus_state(db) is not None


def test_usuario_nao_altera_proprio_papel(db, emulator_host):
    seed(db)
    r = Client(emulator_host, "p1").patch("users/p1", {"role": "dono_frota"})
    assert r.status_code == 403
    assert db.collection("users").document("p1").get().to_dict()["role"] == "passageiro"


def test_leitura_de_perfil_somente_proprio(db, emulator_host):
    seed(db)
    c = Client(emulator_host, "m1")
    assert c.get("users/m1").status_code == 200
    assert c.get("users/m2").status_code == 403


def test_leitura_de_drivers_somente_proprio_ou_dono(db, emulator_host):
    seed(db)
    docs = {d.to_dict()["user_id"]: d.id for d in db.collection("drivers").stream()}
    c = Client(emulator_host, "m1")
    assert c.get(f"drivers/{docs['m1']}").status_code == 200
    assert c.get(f"drivers/{docs['m2']}").status_code == 403
    assert Client(emulator_host, FLEET_A, "dono_frota").get(
        f"drivers/{docs['m2']}").status_code == 200


def test_colecao_desconhecida_negada(db, emulator_host):
    assert Client(emulator_host, "m1").get("segredos/x").status_code == 403


# ---- Custom Claims nas regras ----------------------------------------------
def test_dono_precisa_da_claim_dono_frota_para_ler_drivers(db, emulator_host):
    seed(db)
    docs = {d.to_dict()["user_id"]: d.id for d in db.collection("drivers").stream()}
    path = f"drivers/{docs['m2']}"
    # mesmo uid do dono da frota, mas sem a claim / com outra role: negado
    assert Client(emulator_host, FLEET_A).get(path).status_code == 403
    assert Client(emulator_host, FLEET_A, "motorista").get(path).status_code == 403
    assert Client(emulator_host, FLEET_A, "passageiro").get(path).status_code == 403
    assert Client(emulator_host, FLEET_A, "admin").get(path).status_code == 403
    assert Client(emulator_host, FLEET_A, "dono_frota").get(path).status_code == 200


def test_claim_dono_frota_de_outro_uid_nao_le_drivers_da_frota(db, emulator_host):
    seed(db)
    docs = {d.to_dict()["user_id"]: d.id for d in db.collection("drivers").stream()}
    # role certa, mas fleet_owner_id != uid: a propriedade continua exigida
    c = Client(emulator_host, "usr_df999", "dono_frota")
    assert c.get(f"drivers/{docs['m2']}").status_code == 403


def test_motorista_continua_lendo_o_proprio_cadastro(db, emulator_host):
    seed(db)
    docs = {d.to_dict()["user_id"]: d.id for d in db.collection("drivers").stream()}
    assert Client(emulator_host, "m1", "motorista").get(
        f"drivers/{docs['m1']}").status_code == 200


def test_firestore_role_nao_vale_para_regras(db, emulator_host):
    """users/{uid}.role = dono_frota no Firestore não dá acesso de dono."""
    seed(db)
    make_user(db, FLEET_A, role="dono_frota", fleet=FLEET_A)  # espelho legado
    docs = {d.to_dict()["user_id"]: d.id for d in db.collection("drivers").stream()}
    # token do mesmo uid SEM claim: o espelho do Firestore não é considerado
    assert Client(emulator_host, FLEET_A).get(f"drivers/{docs['m2']}").status_code == 403


def test_claim_nao_permite_escrever_nada(db, emulator_host):
    seed(db)
    before = bus_state(db)
    for role in ("dono_frota", "motorista", "passageiro"):
        c = Client(emulator_host, FLEET_A, role)
        assert c.patch("buses/bus1", {"active_driver_id": "m1"}).status_code == 403
        assert c.patch("users/p1", {"role": "dono_frota"}).status_code == 403
    assert bus_state(db) == before
