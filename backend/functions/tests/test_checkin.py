"""Testes da lógica de check-in contra o Firestore Emulator (15 cenários + extras).

Em toda recusa, além do código/motivo do erro, verificamos que o documento do
ônibus permaneceu exatamente igual.
"""
import threading

import pytest
from google.cloud.firestore import DELETE_FIELD

from checkin import CheckInError, handle_check_in
from conftest import (DONO_FROTA, FLEET_A, FLEET_B, MOTORISTA, PASSAGEIRO,
                      bus_state, make_bus, make_driver, make_driver_record,
                      make_user)

TAG = "TAG-BUS-01"
_UNSET = object()


def checkin(db, uid, data, claims=MOTORISTA):
    """handle_check_in com as claims do token (padrão: role=motorista)."""
    return handle_check_in(db, uid, data, claims)


def refused(db, uid, code, reason, tag=TAG, bus_id="bus1", data=_UNSET,
            claims=MOTORISTA):
    """Executa o check-in esperando recusa e confirma que o ônibus não mudou."""
    before = bus_state(db, bus_id)
    with pytest.raises(CheckInError) as exc:
        handle_check_in(db, uid, {"tagCode": tag} if data is _UNSET else data,
                        claims)
    assert exc.value.code == code
    assert exc.value.reason == reason
    assert bus_state(db, bus_id) == before, "documento do ônibus foi alterado"


# 1
def test_01_checkin_valido(db):
    make_driver(db, "m1")
    make_bus(db)
    res = checkin(db, "m1", {"tagCode": TAG})
    assert res["success"] is True and res["busId"] == "bus1"
    assert bus_state(db)["active_driver_id"] == "m1"
    # demais campos intactos
    s = bus_state(db)
    assert s["plate"] == "HPX-9876" and s["fleet_owner_id"] == FLEET_A


# 2
def test_02_nao_autenticado(db):
    make_driver(db, "m1")
    make_bus(db)
    refused(db, None, "unauthenticated", "unauthenticated")
    refused(db, "", "unauthenticated", "unauthenticated")


# 3
def test_03_usuario_inexistente(db):
    # há cadastro em drivers, mas não existe users/ghost
    make_driver_record(db, "ghost")
    make_bus(db)
    refused(db, "ghost", "not-found", "user_not_found")


# 4
def test_04_passageiro(db):
    make_user(db, "p1", role="passageiro", fleet=None)
    make_driver_record(db, "p1")  # mesmo com cadastro, o papel manda
    make_bus(db)
    refused(db, "p1", "permission-denied", "not_a_driver", claims=PASSAGEIRO)


# 5
def test_05_motorista_sem_cadastro_em_drivers(db):
    make_user(db, "m1")
    make_bus(db)
    refused(db, "m1", "permission-denied", "driver_record_not_found")


# 6
def test_06_cadastro_duplicado(db):
    make_user(db, "m1")
    make_driver_record(db, "m1", doc_id="d1")
    make_driver_record(db, "m1", doc_id="d2")
    make_bus(db)
    refused(db, "m1", "failed-precondition", "duplicate_driver_record")


# 7
def test_07_cadastro_com_user_id_incorreto(db):
    make_user(db, "m1")
    make_driver_record(db, "outro_uid")  # aponta para outro usuário
    make_bus(db)
    refused(db, "m1", "permission-denied", "driver_record_not_found")


# 8
def test_08_motorista_inativo(db):
    make_driver(db, "m1", active=False)
    make_bus(db)
    refused(db, "m1", "permission-denied", "driver_inactive")


# 8b: 'active' deve ser exatamente True (não "true", 1, ausente)
@pytest.mark.parametrize("value", ["true", 1, None])
def test_08b_active_nao_booleano(db, value):
    make_user(db, "m1")
    make_driver_record(db, "m1", active=value)
    make_bus(db)
    refused(db, "m1", "permission-denied", "driver_inactive")


# 9
def test_09_divergencia_fleet_owner_id(db):
    make_user(db, "m1", fleet=FLEET_B)
    make_driver_record(db, "m1", fleet=FLEET_A)
    make_bus(db, fleet=FLEET_A)
    refused(db, "m1", "permission-denied", "fleet_mismatch_driver_user")


# 10
def test_10_tag_inexistente(db):
    make_driver(db, "m1")
    make_bus(db)
    refused(db, "m1", "not-found", "bus_not_found", tag="TAG-NAO-EXISTE")


# 11
def test_11_tag_duplicado(db):
    make_driver(db, "m1")
    make_bus(db, "bus1", TAG)
    make_bus(db, "bus2", TAG)
    refused(db, "m1", "failed-precondition", "duplicate_tag_code")
    assert bus_state(db, "bus2")["active_driver_id"] is None


# 12
def test_12_onibus_de_outra_frota(db):
    make_driver(db, "m1", fleet=FLEET_A)
    make_bus(db, fleet=FLEET_B)
    refused(db, "m1", "permission-denied", "bus_other_fleet")


# 13
def test_13_onibus_ocupado(db):
    make_driver(db, "m1")
    make_driver(db, "m2")
    make_bus(db, active="m2")
    refused(db, "m1", "failed-precondition", "bus_occupied")
    assert bus_state(db)["active_driver_id"] == "m2"


# 14
@pytest.mark.parametrize("rodada", range(5))
def test_14_concorrencia_dois_motoristas(db, rodada):
    """Dois motoristas disputam o mesmo ônibus ao mesmo tempo.

    Cada thread registra SEMPRE um desfecho (sucesso, recusa de negócio ou
    exceção inesperada); nenhuma exceção é engolida nem aceita como "recusa".
    """
    make_driver(db, "mA")
    make_driver(db, "mB")
    make_bus(db)
    before = bus_state(db)
    barrier = threading.Barrier(2, timeout=30)
    outcomes = {}  # uid -> ("ok", dict) | ("refused", CheckInError) | ("error", Exception)

    def worker(uid):
        try:
            barrier.wait()
            outcomes[uid] = ("ok", checkin(db, uid, {"tagCode": TAG}))
        except CheckInError as e:
            outcomes[uid] = ("refused", e)
        except Exception as e:  # noqa: BLE001 - registrar, nunca engolir
            outcomes[uid] = ("error", e)

    threads = [threading.Thread(target=worker, args=(u,), daemon=True)
               for u in ("mA", "mB")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)

    # 1) nenhuma thread travada e ambas registraram desfecho
    assert not any(t.is_alive() for t in threads), \
        f"thread não terminou em 120s: {outcomes}"
    assert set(outcomes) == {"mA", "mB"}, f"desfechos incompletos: {outcomes}"

    # 2) nenhuma exceção inesperada (ex.: ValueError cru, falha de infraestrutura)
    errors = {u: repr(o[1]) for u, o in outcomes.items() if o[0] == "error"}
    assert not errors, f"exceção inesperada nas threads: {errors}"

    # 3) contenção persistente NÃO é recusa válida: é falha de disponibilidade
    contention = [u for u, o in outcomes.items()
                  if o[0] == "refused" and o[1].reason == "contention"]
    assert not contention, (
        "transação abortada por contenção após todas as tentativas "
        f"(lock timeout do emulador?): {contention}. "
        f"Estado do ônibus: {bus_state(db)['active_driver_id']!r}")

    # 4) exatamente um vencedor e um perdedor, com o motivo correto
    winners = [u for u, o in outcomes.items() if o[0] == "ok"]
    losers = [u for u, o in outcomes.items() if o[0] == "refused"]
    assert len(winners) == 1 and len(losers) == 1, outcomes
    assert outcomes[winners[0]][1]["success"] is True
    assert outcomes[losers[0]][1].reason == "bus_occupied", outcomes[losers[0]][1].reason

    # 5) estado final consistente: só o vencedor, nenhum outro campo alterado
    after = bus_state(db)
    assert after["active_driver_id"] == winners[0]
    assert {k: v for k, v in after.items() if k != "active_driver_id"} == \
        {k: v for k, v in before.items() if k != "active_driver_id"}


# 15
def test_15_novo_checkin_apos_liberacao(db):
    make_driver(db, "m1")
    make_driver(db, "m2")
    make_bus(db)
    checkin(db, "m1", {"tagCode": TAG})
    refused(db, "m2", "failed-precondition", "bus_occupied")
    # liberação legítima (feita pelo backend/Admin, ex.: futuro check-out)
    db.collection("buses").document("bus1").update({"active_driver_id": None})
    res = checkin(db, "m2", {"tagCode": TAG})
    assert res["success"] is True
    assert bus_state(db)["active_driver_id"] == "m2"


# ---- extras de segurança ----------------------------------------------------
def test_x1_uid_do_payload_e_ignorado(db):
    make_driver(db, "m1")
    make_driver(db, "vitima")
    make_bus(db)
    checkin(db, "m1", {"tagCode": TAG, "uid": "vitima",
                               "driverId": "vitima"})
    assert bus_state(db)["active_driver_id"] == "m1"


def test_x2_mesmo_motorista_duas_vezes_e_recusado(db):
    make_driver(db, "m1")
    make_bus(db)
    checkin(db, "m1", {"tagCode": TAG})
    refused(db, "m1", "failed-precondition", "already_checked_in_here")


@pytest.mark.parametrize("data", [None, {}, {"tagCode": ""}, {"tagCode": "  "},
                                  {"tagCode": 123}, {"tagCode": "x" * 500}, "TAG"])
def test_x3_tagcode_invalido(db, data):
    make_driver(db, "m1")
    make_bus(db)
    refused(db, "m1", "invalid-argument", "invalid_tag_code", data=data)

# ---- Custom Claims como fonte da role ---------------------------------------
# A role que autoriza é a claim `role` do token. `users/{uid}.role` é só um
# espelho informativo/legado e NÃO pode conceder nem remover permissão.

def test_c1_motorista_com_claim_valida(db):
    make_driver(db, "m1")
    make_bus(db)
    assert checkin(db, "m1", {"tagCode": TAG}, {"role": "motorista"})["success"]
    assert bus_state(db)["active_driver_id"] == "m1"


def test_c1b_outras_claims_nao_atrapalham(db):
    make_driver(db, "m1")
    make_bus(db)
    checkin(db, "m1", {"tagCode": TAG},
            {"role": "motorista", "beta": True, "user_id": "m1", "sub": "m1"})
    assert bus_state(db)["active_driver_id"] == "m1"


def test_c2_passageiro_com_claim(db):
    make_user(db, "p1", role="passageiro", fleet=None)
    make_bus(db)
    refused(db, "p1", "permission-denied", "not_a_driver", claims=PASSAGEIRO)


def test_c3_dono_frota_nao_faz_checkin(db):
    # Dono com users/driver/ônibus da própria frota: a role ainda o impede.
    make_user(db, FLEET_A, role="dono_frota", fleet=FLEET_A)
    make_driver_record(db, FLEET_A, fleet=FLEET_A)
    make_bus(db, fleet=FLEET_A)
    refused(db, FLEET_A, "permission-denied", "not_a_driver", claims=DONO_FROTA)


@pytest.mark.parametrize("claims", [None, {}, {"beta": True}, {"role": None},
                                    "motorista", ["motorista"], 42],
                         ids=["none", "vazio", "so_outra_claim", "role_none",
                              "claims_str", "claims_lista", "claims_int"])
def test_c4_sem_claim_role(db, claims):
    make_driver(db, "m1")  # Firestore diz motorista, mas o token não tem role
    make_bus(db)
    refused(db, "m1", "permission-denied", "missing_role_claim", claims=claims)


@pytest.mark.parametrize("role", ["admin", "MOTORISTA", "Motorista", " motorista",
                                  "motorista ", "", 1, True, ["motorista"],
                                  {"x": 1}])
def test_c5_role_invalida(db, role):
    make_driver(db, "m1")
    make_bus(db)
    refused(db, "m1", "permission-denied", "invalid_role", claims={"role": role})


def test_c6_role_do_firestore_nao_concede_permissao(db):
    # users/p1.role = "motorista" no Firestore + cadastro em drivers,
    # mas a claim do token é passageiro: deve ser recusado.
    make_user(db, "p1", role="motorista", fleet=FLEET_A)
    make_driver_record(db, "p1")
    make_bus(db)
    refused(db, "p1", "permission-denied", "not_a_driver", claims=PASSAGEIRO)


def test_c7_role_do_firestore_nao_remove_permissao(db):
    # Campo legado diz "passageiro", mas a claim oficial é motorista: permitido.
    make_user(db, "m1", role="passageiro", fleet=FLEET_A)
    make_driver_record(db, "m1")
    make_bus(db)
    assert checkin(db, "m1", {"tagCode": TAG}, MOTORISTA)["success"]
    assert bus_state(db)["active_driver_id"] == "m1"


def test_c8_user_sem_campo_role_no_firestore_funciona(db):
    make_user(db, "m1")
    db.collection("users").document("m1").update({"role": DELETE_FIELD})
    make_driver_record(db, "m1")
    make_bus(db)
    assert checkin(db, "m1", {"tagCode": TAG}, MOTORISTA)["success"]


def test_c9_role_no_payload_e_ignorada(db):
    make_user(db, "p1", role="passageiro", fleet=None)
    make_driver_record(db, "p1")
    make_bus(db)
    refused(db, "p1", "permission-denied", "not_a_driver", claims=PASSAGEIRO,
            data={"tagCode": TAG, "role": "motorista",
                  "claims": {"role": "motorista"}, "token": {"role": "motorista"}})


def test_c10_sem_uid_e_recusado_mesmo_com_claim_motorista(db):
    make_driver(db, "m1")
    make_bus(db)
    refused(db, None, "unauthenticated", "unauthenticated", claims=MOTORISTA)


def test_c11_motorista_da_frota_b_nao_usa_onibus_da_frota_a(db):
    make_driver(db, "mB", fleet=FLEET_B)
    make_bus(db, fleet=FLEET_A)
    refused(db, "mB", "permission-denied", "bus_other_fleet", claims=MOTORISTA)


def test_c12_claim_motorista_nao_dispensa_cadastro_em_drivers(db):
    make_user(db, "m1")  # sem drivers/*
    make_bus(db)
    refused(db, "m1", "permission-denied", "driver_record_not_found")


def test_c13_claim_motorista_nao_dispensa_motorista_ativo(db):
    make_driver(db, "m1", active=False)
    make_bus(db)
    refused(db, "m1", "permission-denied", "driver_inactive")


# ---- desvínculo automático de tags antigas ----------------------------------
TAG2 = "TAG-BUS-02"


def owners(db, *bus_ids):
    return {b: bus_state(db, b)["active_driver_id"] for b in bus_ids}


# 16
def test_16_novo_checkin_desvincula_tag_antiga(db):
    make_driver(db, "m1")
    make_bus(db, "bus1", TAG)
    make_bus(db, "bus2", TAG2)
    checkin(db, "m1", {"tagCode": TAG})
    res = checkin(db, "m1", {"tagCode": TAG2})
    assert res["success"] is True and res["busId"] == "bus2"
    assert res["releasedBuses"] == [{"busId": "bus1", "tagCode": TAG}]
    assert owners(db, "bus1", "bus2") == {"bus1": None, "bus2": "m1"}
    # a tag antiga só perde o vínculo; o resto do documento fica intacto
    s = bus_state(db, "bus1")
    assert s["tag_code"] == TAG and s["plate"] == "HPX-9876"


# 17
def test_17_sem_tag_antiga_nada_e_liberado(db):
    make_driver(db, "m1")
    make_bus(db, "bus1", TAG)
    res = checkin(db, "m1", {"tagCode": TAG})
    assert res["releasedBuses"] == []


# 18: dados legados/inconsistentes com várias tags do mesmo motorista
def test_18_varias_tags_antigas_sao_todas_desvinculadas(db):
    make_driver(db, "m1")
    make_bus(db, "bus1", "TAG-A", active="m1")
    make_bus(db, "bus2", "TAG-B", active="m1")
    make_bus(db, "bus3", "TAG-C", active="m1")
    make_bus(db, "bus4", "TAG-D")
    res = checkin(db, "m1", {"tagCode": "TAG-D"})
    assert [r["busId"] for r in res["releasedBuses"]] == ["bus1", "bus2", "bus3"]
    assert owners(db, "bus1", "bus2", "bus3", "bus4") == {
        "bus1": None, "bus2": None, "bus3": None, "bus4": "m1"}


# 19: nunca mexe em ônibus de outros motoristas
def test_19_nao_desvincula_outros_motoristas(db):
    make_driver(db, "m1")
    make_driver(db, "m2")
    make_bus(db, "bus1", TAG, active="m1")
    make_bus(db, "bus2", TAG2, active="m2")
    make_bus(db, "bus3", "TAG-C")
    checkin(db, "m1", {"tagCode": "TAG-C"})
    assert owners(db, "bus1", "bus2", "bus3") == {
        "bus1": None, "bus2": "m2", "bus3": "m1"}


# 20: check-in recusado NÃO pode soltar a tag antiga
@pytest.mark.parametrize("cenario", [
    "bus_occupied", "bus_other_fleet", "bus_not_found", "driver_inactive",
    "already_checked_in_here"])
def test_20_recusa_mantem_tag_antiga(db, cenario):
    make_bus(db, "bus1", TAG, active="m1")  # tag antiga de m1
    make_bus(db, "bus2", TAG2)
    if cenario == "driver_inactive":
        make_driver(db, "m1", active=False)
    else:
        make_driver(db, "m1")
    target = TAG2
    if cenario == "bus_occupied":
        make_driver(db, "m2")
        make_bus(db, "bus2", TAG2, active="m2")
    elif cenario == "bus_other_fleet":
        make_bus(db, "bus2", TAG2, fleet=FLEET_B)
    elif cenario == "bus_not_found":
        target = "TAG-NAO-EXISTE"
    elif cenario == "already_checked_in_here":
        target = TAG  # já está em bus1
    before = owners(db, "bus1", "bus2")
    with pytest.raises(CheckInError):
        checkin(db, "m1", {"tagCode": target})
    assert owners(db, "bus1", "bus2") == before
    assert bus_state(db, "bus1")["active_driver_id"] == "m1"


# 21
def test_21_sequencia_a_b_c_deixa_so_o_ultimo(db):
    make_driver(db, "m1")
    for i, tag in enumerate(("TAG-A", "TAG-B", "TAG-C"), 1):
        make_bus(db, f"bus{i}", tag)
    for tag in ("TAG-A", "TAG-B", "TAG-C"):
        checkin(db, "m1", {"tagCode": tag})
    assert owners(db, "bus1", "bus2", "bus3") == {
        "bus1": None, "bus2": None, "bus3": "m1"}


# 22
def test_22_tag_antiga_fica_livre_para_outro_motorista(db):
    make_driver(db, "m1")
    make_driver(db, "m2")
    make_bus(db, "bus1", TAG)
    make_bus(db, "bus2", TAG2)
    checkin(db, "m1", {"tagCode": TAG})
    checkin(db, "m1", {"tagCode": TAG2})
    res = checkin(db, "m2", {"tagCode": TAG})
    assert res["success"] is True
    assert owners(db, "bus1", "bus2") == {"bus1": "m2", "bus2": "m1"}


# 23
@pytest.mark.parametrize("rodada", range(5))
def test_23_concorrencia_mesmo_motorista_em_dois_onibus(db, rodada):
    """O mesmo motorista faz check-in em dois ônibus ao mesmo tempo.

    Os dois podem ter sucesso (um depois do outro, o segundo desvincula o
    primeiro) ou um deles pode ser recusado, mas NUNCA o motorista pode
    terminar vinculado a mais de um ônibus.
    """
    make_driver(db, "m1")
    make_bus(db, "bus1", TAG)
    make_bus(db, "bus2", TAG2)
    barrier = threading.Barrier(2, timeout=30)
    outcomes = {}

    def worker(tag):
        try:
            barrier.wait()
            outcomes[tag] = ("ok", checkin(db, "m1", {"tagCode": tag}))
        except CheckInError as e:
            outcomes[tag] = ("refused", e)
        except Exception as e:  # noqa: BLE001 - registrar, nunca engolir
            outcomes[tag] = ("error", e)

    threads = [threading.Thread(target=worker, args=(t,), daemon=True)
               for t in (TAG, TAG2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)

    assert not any(t.is_alive() for t in threads), outcomes
    assert set(outcomes) == {TAG, TAG2}, outcomes
    errors = {t: repr(o[1]) for t, o in outcomes.items() if o[0] == "error"}
    assert not errors, errors
    assert any(o[0] == "ok" for o in outcomes.values()), outcomes
    vinculados = [b for b, uid in owners(db, "bus1", "bus2").items() if uid == "m1"]
    assert len(vinculados) == 1, (
        f"motorista ficou em {vinculados}; desfechos: {outcomes}")
