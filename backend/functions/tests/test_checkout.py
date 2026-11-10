"""Testes do check-out (fim de expediente) contra o Firestore Emulator.

Incluem o cenário do relato do time: com todos os ônibus da frota ocupados,
ninguém conseguia fazer check-in porque não havia como liberar um ônibus.

Autorização: como no check-in, a role OFICIAL é a custom claim `role` do token
(`users/{uid}.role` no Firestore é só informativo). O check-out NÃO consulta
`drivers`/`active`: motorista desativado depois do check-in ainda libera o
próprio ônibus.
"""
import threading

import pytest

from checkin import CheckInError, handle_check_in, handle_check_out
from conftest import (DONO_FROTA, FLEET_B, MOTORISTA, PASSAGEIRO, bus_state,
                      make_bus, make_driver, make_driver_record, make_user)

TAG, TAG2, TAG3 = "TAG-BUS-01", "TAG-BUS-02", "TAG-BUS-03"


def checkout(db, uid, claims=MOTORISTA):
    """handle_check_out com as claims do token (padrão: role=motorista)."""
    return handle_check_out(db, uid, claims)


def checkin(db, uid, data, claims=MOTORISTA):
    return handle_check_in(db, uid, data, claims)


def owners(db, *bus_ids):
    return {b: bus_state(db, b)["active_driver_id"] for b in bus_ids}


def refused(db, uid, code, reason, claims=MOTORISTA):
    with pytest.raises(CheckInError) as exc:
        checkout(db, uid, claims)
    assert exc.value.code == code, exc.value.code
    assert exc.value.reason == reason, exc.value.reason


# 24
def test_24_checkout_libera_o_onibus(db):
    make_driver(db, "m1")
    make_bus(db, "bus1", TAG, active="m1")
    before = bus_state(db, "bus1")
    res = checkout(db, "m1")
    assert res["success"] is True and res["driverId"] == "m1"
    assert res["releasedBuses"] == [{"busId": "bus1", "tagCode": TAG}]
    assert res["message"] == "Check-out realizado com sucesso."
    after = bus_state(db, "bus1")
    assert after["active_driver_id"] is None
    # só o vínculo muda; o resto do documento fica intacto
    assert {k: v for k, v in after.items() if k != "active_driver_id"} == \
        {k: v for k, v in before.items() if k != "active_driver_id"}


# 25: idempotente (botão apertado duas vezes, retry do app)
def test_25_checkout_sem_onibus_e_idempotente(db):
    make_driver(db, "m1")
    make_bus(db, "bus1", TAG)
    for _ in range(2):
        res = checkout(db, "m1")
        assert res["success"] is True and res["releasedBuses"] == []
        assert res["message"] == "Nenhum ônibus vinculado a você."
    assert owners(db, "bus1") == {"bus1": None}


# 26
def test_26_checkout_nao_afeta_outros_motoristas(db):
    make_driver(db, "m1")
    make_driver(db, "m2")
    make_bus(db, "bus1", TAG, active="m1")
    make_bus(db, "bus2", TAG2, active="m2")
    checkout(db, "m1")
    assert owners(db, "bus1", "bus2") == {"bus1": None, "bus2": "m2"}


# 27: dados legados com várias tags do mesmo motorista
def test_27_checkout_libera_todas_as_tags_do_motorista(db):
    make_driver(db, "m1")
    make_bus(db, "bus1", TAG, active="m1")
    make_bus(db, "bus2", TAG2, active="m1")
    make_bus(db, "bus3", TAG3)
    res = checkout(db, "m1")
    assert [r["busId"] for r in res["releasedBuses"]] == ["bus1", "bus2"]
    assert owners(db, "bus1", "bus2", "bus3") == {
        "bus1": None, "bus2": None, "bus3": None}


# 28: sem identidade verificada (uid ausente/ inválido), mesmo com claims válidas
@pytest.mark.parametrize("uid", [None, "", 123])
def test_28_checkout_nao_autenticado(db, uid):
    make_driver(db, "m1")
    make_bus(db, "bus1", TAG, active="m1")
    refused(db, uid, "unauthenticated", "unauthenticated")
    assert owners(db, "bus1") == {"bus1": "m1"}


def test_28b_checkout_sem_uid_e_sem_claims_e_unauthenticated(db):
    # Chamada anônima de verdade (req.auth is None): uid=None e claims=None.
    make_driver(db, "m1")
    make_bus(db, "bus1", TAG, active="m1")
    refused(db, None, "unauthenticated", "unauthenticated", claims=None)
    assert owners(db, "bus1") == {"bus1": "m1"}


# 29: o cenário do relato do time
def test_29_frota_toda_ocupada_volta_a_funcionar_apos_checkout(db):
    make_driver(db, "m1")
    make_driver(db, "m2")
    make_bus(db, "bus1", TAG, active="m1")
    make_bus(db, "bus2", TAG2, fleet=FLEET_B)  # de outra frota
    make_bus(db, "bus3", TAG3, active="m2")
    # sem check-out: m2 não consegue o ônibus do m1 e m1 não consegue o do m2
    with pytest.raises(CheckInError) as exc:
        checkin(db, "m2", {"tagCode": TAG})
    assert exc.value.reason == "bus_occupied"
    with pytest.raises(CheckInError) as exc:
        checkin(db, "m1", {"tagCode": TAG3})
    assert exc.value.reason == "bus_occupied"
    # m1 encerra o expediente: o ônibus volta a ficar disponível
    checkout(db, "m1")
    res = checkin(db, "m2", {"tagCode": TAG})
    assert res["success"] is True
    # e m2 foi desvinculado do ônibus antigo pela regra de desvínculo
    assert res["releasedBuses"] == [{"busId": "bus3", "tagCode": TAG3}]
    assert owners(db, "bus1", "bus3") == {"bus1": "m2", "bus3": None}


# 30: motorista desativado/demitido não deixa ônibus preso
def test_30_motorista_inativo_consegue_liberar_o_proprio_onibus(db):
    make_driver(db, "m1", active=False)
    make_bus(db, "bus1", TAG, active="m1")
    res = checkout(db, "m1")
    assert res["releasedBuses"] == [{"busId": "bus1", "tagCode": TAG}]
    assert owners(db, "bus1") == {"bus1": None}


def test_30b_motorista_sem_cadastro_em_drivers_tambem_libera_o_proprio(db):
    # O check-out não depende de `drivers`: cadastro removido não prende o ônibus.
    make_user(db, "m1")
    make_bus(db, "bus1", TAG, active="m1")
    checkout(db, "m1")
    assert owners(db, "bus1") == {"bus1": None}


# 31
def test_31_apos_checkout_o_mesmo_motorista_pode_voltar(db):
    make_driver(db, "m1")
    make_bus(db, "bus1", TAG)
    checkin(db, "m1", {"tagCode": TAG})
    checkout(db, "m1")
    res = checkin(db, "m1", {"tagCode": TAG})
    assert res["success"] is True
    assert owners(db, "bus1") == {"bus1": "m1"}


# ---- Autorização: a role OFICIAL é a claim `role` do token -------------------
# 33
@pytest.mark.parametrize("claims", [None, {}, {"beta": True}, {"role": None},
                                    "motorista", ["motorista"], 42],
                         ids=["none", "vazio", "so_outra_claim", "role_none",
                              "claims_str", "claims_lista", "claims_int"])
def test_33_checkout_sem_claim_role(db, claims):
    make_driver(db, "m1")  # Firestore diz motorista, mas o token não tem role
    make_bus(db, "bus1", TAG, active="m1")
    refused(db, "m1", "permission-denied", "missing_role_claim", claims=claims)
    assert owners(db, "bus1") == {"bus1": "m1"}


# 34
@pytest.mark.parametrize("role", ["admin", "MOTORISTA", "Motorista", " motorista",
                                  "motorista ", "", 1, True, ["motorista"],
                                  {"x": 1}])
def test_34_checkout_role_invalida(db, role):
    make_driver(db, "m1")
    make_bus(db, "bus1", TAG, active="m1")
    refused(db, "m1", "permission-denied", "invalid_role", claims={"role": role})
    assert owners(db, "bus1") == {"bus1": "m1"}


# 35
@pytest.mark.parametrize("claims", [PASSAGEIRO, DONO_FROTA],
                         ids=["passageiro", "dono_frota"])
def test_35_checkout_so_para_motorista(db, claims):
    make_driver(db, "m1")
    make_bus(db, "bus1", TAG, active="m1")
    refused(db, "m1", "permission-denied", "not_a_driver", claims=claims)
    assert owners(db, "bus1") == {"bus1": "m1"}


# 36: `users/{uid}.role` no Firestore não concede nem remove permissão
def test_36a_role_do_firestore_nao_concede_permissao(db):
    make_user(db, "p1", role="motorista")  # espelho legado diz motorista
    make_bus(db, "bus1", TAG, active="p1")
    refused(db, "p1", "permission-denied", "not_a_driver", claims=PASSAGEIRO)
    assert owners(db, "bus1") == {"bus1": "p1"}


def test_36b_role_do_firestore_nao_remove_permissao(db):
    make_user(db, "m1", role="passageiro")  # espelho legado diz passageiro
    make_driver_record(db, "m1")
    make_bus(db, "bus1", TAG, active="m1")
    assert checkout(db, "m1", MOTORISTA)["success"]
    assert owners(db, "bus1") == {"bus1": None}


# 37: com claim válida, só o PRÓPRIO uid é liberado (nunca o de outro motorista)
def test_37_motorista_nao_consegue_liberar_onibus_de_outro(db):
    make_driver(db, "m1")
    make_driver(db, "m2")
    make_bus(db, "bus1", TAG, active="m1")
    make_bus(db, "bus2", TAG2, active="m2")
    res = checkout(db, "m2")
    assert res["releasedBuses"] == [{"busId": "bus2", "tagCode": TAG2}]
    assert owners(db, "bus1", "bus2") == {"bus1": "m1", "bus2": None}


# ---- Concorrência ------------------------------------------------------------
def _run_threads(*targets):
    threads = [threading.Thread(target=t, daemon=True) for t in targets]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
    assert not any(t.is_alive() for t in threads)


def _no_unexpected_errors(outcomes):
    """Aceita sucesso, recusa de negócio e `contention`; qualquer outra coisa falha."""
    bad = {k: repr(o[1]) for k, o in outcomes.items() if o[0] == "error"}
    assert not bad, bad


# 32
@pytest.mark.parametrize("rodada", range(5))
def test_32_concorrencia_checkout_e_checkin_do_mesmo_motorista(db, rodada):
    """Check-out e check-in do mesmo motorista ao mesmo tempo.

    Qualquer ordem de execução é válida, mas o motorista nunca pode terminar
    vinculado a mais de um ônibus, e nenhuma exceção inesperada é aceita.
    """
    make_driver(db, "m1")
    make_bus(db, "bus1", TAG, active="m1")
    make_bus(db, "bus2", TAG2)
    barrier = threading.Barrier(2, timeout=30)
    outcomes = {}

    def do_checkout():
        try:
            barrier.wait()
            outcomes["out"] = ("ok", checkout(db, "m1"))
        except CheckInError as e:
            outcomes["out"] = ("refused", e)
        except Exception as e:  # noqa: BLE001 - registrar, nunca engolir
            outcomes["out"] = ("error", e)

    def do_checkin():
        try:
            barrier.wait()
            outcomes["in"] = ("ok", checkin(db, "m1", {"tagCode": TAG2}))
        except CheckInError as e:
            outcomes["in"] = ("refused", e)
        except Exception as e:  # noqa: BLE001
            outcomes["in"] = ("error", e)

    _run_threads(do_checkout, do_checkin)
    assert set(outcomes) == {"out", "in"}, outcomes
    _no_unexpected_errors(outcomes)
    for o in outcomes.values():  # só `contention` é recusa aceitável aqui
        if o[0] == "refused":
            assert o[1].reason == "contention", repr(o[1])
    vinculados = [b for b, uid in owners(db, "bus1", "bus2").items() if uid == "m1"]
    assert len(vinculados) <= 1, f"{vinculados}; desfechos: {outcomes}"


# 38: dois check-outs do mesmo motorista ao mesmo tempo (duplo toque no botão)
@pytest.mark.parametrize("rodada", range(5))
def test_38_concorrencia_dois_checkouts_do_mesmo_motorista(db, rodada):
    make_driver(db, "m1")
    make_bus(db, "bus1", TAG, active="m1")
    barrier = threading.Barrier(2, timeout=30)
    outcomes = {}

    def worker(name):
        try:
            barrier.wait()
            outcomes[name] = ("ok", checkout(db, "m1"))
        except CheckInError as e:
            outcomes[name] = ("refused", e)
        except Exception as e:  # noqa: BLE001
            outcomes[name] = ("error", e)

    _run_threads(lambda: worker("a"), lambda: worker("b"))
    assert set(outcomes) == {"a", "b"}, outcomes
    _no_unexpected_errors(outcomes)
    oks = [o[1] for o in outcomes.values() if o[0] == "ok"]
    assert oks, outcomes
    assert owners(db, "bus1") == {"bus1": None}
    # o ônibus é reportado como liberado no máximo uma vez
    assert sum(len(r["releasedBuses"]) for r in oks) <= 1, oks


# 39: check-out do dono atual enquanto OUTRO motorista tenta ocupar o mesmo ônibus
@pytest.mark.parametrize("rodada", range(5))
def test_39_concorrencia_checkout_do_dono_e_checkin_de_outro(db, rodada):
    """m1 libera o bus1 enquanto m2 tenta ocupá-lo.

    Desfechos válidos: m2 recusado (`bus_occupied`/`contention`) e bus1 livre,
    ou m2 consegue e bus1 fica com m2. O check-out de m1 nunca pode apagar o
    vínculo de m2, e bus1 nunca fica com m1.
    """
    make_driver(db, "m1")
    make_driver(db, "m2")
    make_bus(db, "bus1", TAG, active="m1")
    barrier = threading.Barrier(2, timeout=30)
    outcomes = {}

    def do_checkout():
        try:
            barrier.wait()
            outcomes["out"] = ("ok", checkout(db, "m1"))
        except CheckInError as e:
            outcomes["out"] = ("refused", e)
        except Exception as e:  # noqa: BLE001
            outcomes["out"] = ("error", e)

    def do_checkin():
        try:
            barrier.wait()
            outcomes["in"] = ("ok", checkin(db, "m2", {"tagCode": TAG}))
        except CheckInError as e:
            outcomes["in"] = ("refused", e)
        except Exception as e:  # noqa: BLE001
            outcomes["in"] = ("error", e)

    _run_threads(do_checkout, do_checkin)
    assert set(outcomes) == {"out", "in"}, outcomes
    _no_unexpected_errors(outcomes)
    if outcomes["in"][0] == "refused":
        assert outcomes["in"][1].reason in ("bus_occupied", "contention"), \
            repr(outcomes["in"][1])
    owner = owners(db, "bus1")["bus1"]
    if outcomes["out"][0] == "ok":
        # check-out concluído: bus1 nunca fica com m1
        assert owner in (None, "m2"), f"bus1 ficou com {owner}; desfechos: {outcomes}"
    if outcomes["in"][0] == "ok":
        assert owner == "m2", outcomes
