"""Telemetria/heartbeat: lógica de negócio contra Firestore + Realtime Database
Emulators. Relógio SIMULADO: todo instante é um inteiro em ms passado às
funções (`server_now`), então nenhum teste espera 45 s reais.

Rode com `.\\scripts\\test-telemetry.ps1`.
"""
import os
import subprocess
import sys

import pytest

import telemetry
from telemetry import TelemetryError
from conftest import (DONO_FROTA, FLEET_B, MOTORISTA, PASSAGEIRO, PROJECT,
                      make_bus, make_driver)
from rtdb_support import (SKIP_REASON, SUBPROCESS_OK, db_available,
                          telemetry_root)

pytestmark = pytest.mark.skipif(not db_available(), reason=SKIP_REASON)

NOW = 1_800_000_000_000  # instante fixo (ms) usado como "agora" nos testes
EXPECTED_KEYS = {"lat", "lng", "speed", "heading", "status", "updated_at",
                 "is_online", "connection_status", "captured_at"}
# A partir da 2ª atualização válida o nó também guarda a posição anterior.
KEYS_WITH_PREV = EXPECTED_KEYS | {"lat_anterior", "long_anterior"}
_UNSET = object()
_DEL = object()  # em payload(): remove o campo


# ------------------------------------------------------------------- helpers
def payload(bus="bus_01", **over):
    d = {"busId": bus, "lat": -3.6667, "lng": -45.38, "speed": 32.5,
         "heading": 180, "status": "in_service"}
    for k, v in over.items():
        if v is _DEL:
            d.pop(k, None)
        else:
            d[k] = v
    return d


def send(db, root, uid="m1", data=_UNSET, claims=MOTORISTA, now=NOW):
    data = payload() if data is _UNSET else data
    return telemetry.handle_send_telemetry(db, root, uid, data, claims,
                                           server_now=now)


def node(root, bus="bus_01"):
    return root.child(bus).get()


# ------------------------------------------------------------------ fixtures
@pytest.fixture
def root():
    r = telemetry_root()
    r.delete()  # /telemetry limpo a cada teste
    return r


@pytest.fixture
def world(db, root):
    """m1 em check-in no bus_01, m2 no bus_02 (frota A); extras para os
    cenários de autorização negada. Devolve a referência de /telemetry."""
    make_driver(db, "m1")
    make_driver(db, "m2")
    make_driver(db, "m3", active=False)  # cadastro inativo
    make_bus(db, "bus_01", tag="TAG-01", active="m1")
    make_bus(db, "bus_02", tag="TAG-02", active="m2")
    make_bus(db, "bus_03", tag="TAG-03", active="m3")
    make_bus(db, "bus_b", tag="TAG-B", fleet=FLEET_B, active="m1")  # outra frota
    return root


# =================================================== 1-3: gravação / isolamento
def test_registra_telemetria_valida(db, world):
    out = send(db, world)
    n = node(world)
    assert set(n) == EXPECTED_KEYS
    # speed (GPS instantâneo, km/h) é gravado como inteiro: 32.5 -> 33
    assert (n["lat"], n["lng"], n["speed"], n["heading"], n["status"]) == (
        -3.6667, -45.38, 33, 180, "in_service")
    assert isinstance(n["speed"], int)
    # 1ª atualização: sem posição anterior (campos omitidos, nada inventado)
    assert "lat_anterior" not in n and "long_anterior" not in n
    assert n["updated_at"] == NOW  # carimbo do SERVIDOR
    assert n["is_online"] is True and n["connection_status"] == "online"
    assert out == {"success": True, "busId": "bus_01", "updated_at": NOW,
                   "is_online": True, "connection_status": "online"}


def test_atualiza_localizacao_sem_perder_campos(db, world):
    send(db, world)
    send(db, world, data=payload(lat=-3.7, lng=-45.5, speed=10, heading=90,
                                 status="delayed"), now=NOW + 15_000)
    n = node(world)
    assert set(n) == KEYS_WITH_PREV
    assert (n["lat"], n["lng"], n["speed"], n["heading"], n["status"]) == (
        -3.7, -45.5, 10, 90, "delayed")
    assert (n["lat_anterior"], n["long_anterior"]) == (-3.6667, -45.38)
    assert n["updated_at"] == NOW + 15_000
    assert n["is_online"] is True and n["connection_status"] == "online"


def test_posicao_anterior_encadeia_e_ignora_fix_recusado(db, world):
    send(db, world, data=payload(lat=-3.1, lng=-45.1))
    send(db, world, data=payload(lat=-3.2, lng=-45.2), now=NOW + 15_000)
    with pytest.raises(TelemetryError):  # inválido: não pode mexer na anterior
        send(db, world, data=payload(lat=999), now=NOW + 20_000)
    send(db, world, data=payload(lat=-3.3, lng=-45.3), now=NOW + 30_000)
    n = node(world)
    assert (n["lat"], n["lng"]) == (-3.3, -45.3)
    assert (n["lat_anterior"], n["long_anterior"]) == (-3.2, -45.2)


def test_posicao_anterior_preservada_apos_perda_de_conexao(db, world):
    send(db, world, data=payload(lat=-3.1, lng=-45.1))
    send(db, world, data=payload(lat=-3.2, lng=-45.2), now=NOW + 15_000)
    telemetry.sweep(world, NOW + 100_000)  # connection_lost
    n = node(world)
    assert (n["lat_anterior"], n["long_anterior"]) == (-3.1, -45.1)
    send(db, world, data=payload(lat=-3.4, lng=-45.4), now=NOW + 100_000)
    n = node(world)
    assert (n["lat_anterior"], n["long_anterior"]) == (-3.2, -45.2)


def test_no_antigo_sem_coordenadas_validas_omite_anterior(db, world):
    world.child("bus_01").set({"lat": "x", "updated_at": NOW - 1})
    send(db, world)
    assert "lat_anterior" not in node(world)


def test_speed_arredonda_para_inteiro_kmh(db, world):
    for i, (raw, want) in enumerate([(0, 0), (0.4, 0), (0.5, 1), (32.4, 32),
                                     (32.5, 33), (199.6, 200)]):
        send(db, world, data=payload(speed=raw), now=NOW + 15_000 * i)
        n = node(world)
        assert n["speed"] == want and isinstance(n["speed"], int), raw


def test_posicao_anterior_com_atualizacoes_concorrentes(db, world):
    """Uma atualização entra entre a leitura e a escrita: o CAS falha, relê e a
    anterior passa a ser a posição que acabou de chegar (sem perda)."""
    send(db, world, data=payload(lat=-3.1, lng=-45.1))
    ref = world.child("bus_01")
    real = ref.__class__.set_if_unchanged
    fired = []

    def racing(self, etag, value):
        if not fired:
            fired.append(1)  # simula a chegada concorrente antes do 1º CAS
            other = telemetry._next_node(
                self.get(), telemetry.parse_payload(
                    payload(lat=-3.2, lng=-45.2)), NOW + 10_000)
            real(self, self.get(etag=True)[1], other)
        return real(self, etag, value)

    ref.__class__.set_if_unchanged = racing
    try:
        send(db, world, data=payload(lat=-3.3, lng=-45.3), now=NOW + 15_000)
    finally:
        ref.__class__.set_if_unchanged = real
    n = node(world)
    assert (n["lat"], n["lng"]) == (-3.3, -45.3)
    assert (n["lat_anterior"], n["long_anterior"]) == (-3.2, -45.2)


# ----------------------- cálculos puros: distância, ETA e horário previsto ----
def test_haversine_km():
    assert telemetry.haversine_km(-3.6, -45.3, -3.6, -45.3) == 0
    # 1 grau de latitude ~ 111,195 km (raio médio 6371,0088 km)
    assert telemetry.haversine_km(0, 0, 1, 0) == pytest.approx(111.195, abs=0.01)
    # simétrica
    a = telemetry.haversine_km(-3.6667, -45.38, -3.7, -45.5)
    b = telemetry.haversine_km(-3.7, -45.5, -3.6667, -45.38)
    assert a == pytest.approx(b) and a == pytest.approx(13.82, abs=0.05)


def test_eta_minutes():
    assert telemetry.eta_minutes(2.5, 30) == 5          # 2,5/30 h = 5 min
    assert telemetry.eta_minutes(1, 40) == 2            # 1,5 min -> 2
    assert telemetry.eta_minutes(0, 30) == 0


@pytest.mark.parametrize("dist,speed", [
    (2.5, 0), (2.5, -5), (2.5, None), (2.5, float("nan")), (2.5, float("inf")),
    (2.5, "30"), (2.5, True), (None, 30), (-1, 30), (float("nan"), 30),
    ("2", 30)])
def test_eta_indisponivel_sem_previsao_numerica(dist, speed):
    assert telemetry.eta_minutes(dist, speed) is None


def test_horario_previsto_usa_instante_do_servidor_em_ms():
    assert telemetry.predicted_arrival_ms(NOW, 5) == NOW + 300_000
    assert telemetry.predicted_arrival_ms(NOW, 0) == NOW
    assert telemetry.predicted_arrival_ms(NOW, None) is None
    assert telemetry.predicted_arrival_ms(NOW, True) is None


def test_veiculos_independentes(db, world):
    send(db, world, uid="m1", data=payload("bus_01", lat=-3.1), now=NOW)
    send(db, world, uid="m2", data=payload("bus_02", lat=-3.2), now=NOW + 1_000)
    bus2_before = node(world, "bus_02")
    send(db, world, uid="m1", data=payload("bus_01", lat=-3.15), now=NOW + 15_000)
    assert set(world.get()) == {"bus_01", "bus_02"}
    assert node(world, "bus_02") == bus2_before  # intacto
    assert node(world, "bus_01")["lat"] == -3.15


# ====================================================== 4-7: regra dos 45 s
def test_idade_menor_que_45s_continua_online(db, world):
    send(db, world)
    res = telemetry.sweep(world, NOW + 44_999)
    assert res.checked == 0 and res.marked_lost == [] and res.errors == []
    assert node(world)["is_online"] is True


def test_idade_exatamente_45s_nao_perde_conexao(db, world):
    send(db, world)
    res = telemetry.sweep(world, NOW + 45_000)  # regra: estritamente > 45 s
    assert res.marked_lost == [] and res.checked == 0
    n = node(world)
    assert n["is_online"] is True and n["connection_status"] == "online"


def test_reavaliacao_do_no_tambem_respeita_o_limite_estrito(db, world):
    """Segunda defesa (além da consulta): expire_node relê o nó e decide."""
    send(db, world)
    assert telemetry.expire_node(world, "bus_01", NOW + 45_000) == "fresh"
    assert node(world)["is_online"] is True
    assert telemetry.expire_node(world, "bus_01", NOW + 45_001) == "lost"
    assert node(world)["connection_status"] == "connection_lost"


def test_idade_acima_de_45s_perde_conexao(db, world):
    send(db, world)
    before = node(world)
    res = telemetry.sweep(world, NOW + 45_001)
    assert res.marked_lost == ["bus_01"] and res.errors == []
    n = node(world)
    assert n["is_online"] is False and n["connection_status"] == "connection_lost"
    # a posição e o horário da última atualização válida são preservados
    assert {k: v for k, v in n.items() if k not in ("is_online", "connection_status")} \
        == {k: v for k, v in before.items() if k not in ("is_online", "connection_status")}
    # varrer de novo é idempotente (não reescreve nem reporta)
    again = telemetry.sweep(world, NOW + 90_000)
    assert again.marked_lost == [] and node(world) == n


def test_nova_atualizacao_valida_restaura_conexao(db, world):
    send(db, world)
    telemetry.sweep(world, NOW + 60_000)
    assert node(world)["connection_status"] == "connection_lost"
    send(db, world, data=payload(lat=-3.9), now=NOW + 60_000)
    n = node(world)
    assert n["is_online"] is True and n["connection_status"] == "online"
    assert n["updated_at"] == NOW + 60_000 and n["lat"] == -3.9
    assert telemetry.sweep(world, NOW + 60_000 + 44_000).marked_lost == []
    assert telemetry.sweep(world, NOW + 60_000 + 46_000).marked_lost == ["bus_01"]


# ==================================================== 8: validação de dados
INVALID = [
    ("lat_91", {"lat": 91}, "invalid_lat"),
    ("lat_-90.5", {"lat": -90.5}, "invalid_lat"),
    ("lat_texto", {"lat": "10"}, "invalid_lat"),
    ("lat_none", {"lat": None}, "invalid_lat"),
    ("lat_nan", {"lat": float("nan")}, "invalid_lat"),
    ("lat_inf", {"lat": float("inf")}, "invalid_lat"),
    ("lat_bool", {"lat": True}, "invalid_lat"),
    ("lat_ausente", {"lat": _DEL}, "invalid_lat"),
    ("lng_181", {"lng": 181}, "invalid_lng"),
    ("lng_-180.1", {"lng": -180.1}, "invalid_lng"),
    ("lng_nan", {"lng": float("nan")}, "invalid_lng"),
    ("null_island", {"lat": 0, "lng": 0}, "null_island"),
    ("speed_negativa", {"speed": -1}, "invalid_speed"),
    ("speed_201", {"speed": 201}, "invalid_speed"),
    ("speed_inf", {"speed": float("inf")}, "invalid_speed"),
    ("speed_texto", {"speed": "rapido"}, "invalid_speed"),
    ("speed_ausente", {"speed": _DEL}, "invalid_speed"),
    ("heading_360", {"heading": 360}, "invalid_heading"),
    ("heading_negativo", {"heading": -0.1}, "invalid_heading"),
    ("heading_nan", {"heading": float("nan")}, "invalid_heading"),
    ("status_desconhecido", {"status": "parked"}, "invalid_status"),
    ("status_none", {"status": None}, "invalid_status"),
    ("status_numero", {"status": 1}, "invalid_status"),
    ("status_ausente", {"status": _DEL}, "invalid_status"),
    ("busid_com_barra", {"busId": "../x"}, "invalid_bus_id"),
    ("busid_vazio", {"busId": ""}, "invalid_bus_id"),
    ("busid_ausente", {"busId": _DEL}, "invalid_bus_id"),
    ("cliente_forja_is_online", {"is_online": True}, "unexpected_field"),
    ("cliente_forja_connection", {"connection_status": "online"}, "unexpected_field"),
    ("cliente_forja_updated_at", {"updated_at": NOW}, "unexpected_field"),
    ("cliente_forja_uid", {"uid": "m1"}, "unexpected_field"),
    ("captured_at_negativo", {"captured_at": -5}, "invalid_captured_at"),
    ("captured_at_texto", {"captured_at": "x"}, "invalid_captured_at"),
    ("captured_at_bool", {"captured_at": True}, "invalid_captured_at"),
]


@pytest.mark.parametrize("over,reason", [(o, r) for _, o, r in INVALID],
                         ids=[i for i, _, _ in INVALID])
def test_rejeita_dados_invalidos(db, world, over, reason):
    with pytest.raises(TelemetryError) as ei:
        send(db, world, data=payload(**over))
    assert ei.value.reason == reason
    assert world.get() is None  # nada foi gravado


@pytest.mark.parametrize("bad", ["oi", [], 42, None], ids=["str", "lista", "num", "none"])
def test_rejeita_payload_que_nao_e_objeto(db, world, bad):
    with pytest.raises(TelemetryError) as ei:
        send(db, world, data=bad)
    assert ei.value.reason == "invalid_payload"
    assert world.get() is None


def test_limites_validos_sao_aceitos(db, world):
    send(db, world, data=payload(lat=-90, lng=180, speed=0, heading=0))
    send(db, world, data=payload(lat=90, lng=-180, speed=200, heading=359.9),
         now=NOW + 15_000)
    n = node(world)
    assert (n["lat"], n["lng"], n["speed"], n["heading"]) == (90, -180, 200, 359.9)
    assert (n["lat_anterior"], n["long_anterior"]) == (-90, 180)


# ============================================ 9: timestamps / ordem de chegada
def test_atualizacao_antiga_nao_sobrescreve_a_mais_recente(db, world):
    send(db, world, data=payload(captured_at=NOW), now=NOW)
    before = node(world)
    with pytest.raises(TelemetryError) as ei:  # fix capturado ANTES, chegou depois
        send(db, world, data=payload(captured_at=NOW - 1_000, lat=1.0), now=NOW + 1_000)
    assert ei.value.reason == "stale_update"
    with pytest.raises(TelemetryError) as ei:  # repetição exata (retry de rede)
        send(db, world, data=payload(captured_at=NOW, lat=2.0), now=NOW + 2_000)
    assert ei.value.reason == "stale_update"
    assert node(world) == before
    send(db, world, data=payload(captured_at=NOW + 5_000, lat=-3.7), now=NOW + 6_000)
    n = node(world)
    assert n["lat"] == -3.7 and n["captured_at"] == NOW + 5_000
    assert n["updated_at"] == NOW + 6_000


def test_fix_atrasado_nao_vira_heartbeat(db, world):
    with pytest.raises(TelemetryError) as ei:
        send(db, world, data=payload(captured_at=NOW - 45_001), now=NOW)
    assert ei.value.reason == "stale_fix"
    assert world.get() is None
    send(db, world, data=payload(captured_at=NOW - 45_000), now=NOW)  # limite: ok
    assert node(world)["updated_at"] == NOW  # carimbo do servidor, não do celular


def test_relogio_do_celular_no_futuro_nao_mantem_online(db, world):
    with pytest.raises(TelemetryError) as ei:
        send(db, world, data=payload(captured_at=NOW + 10_001), now=NOW)
    assert ei.value.reason == "captured_at_in_future"
    assert world.get() is None
    send(db, world, data=payload(captured_at=NOW + 10_000), now=NOW)  # tolerância
    n = node(world)
    assert n["updated_at"] == NOW  # nunca o valor informado pelo cliente
    # e, sem novos heartbeats, o veículo cai normalmente apesar do captured_at futuro
    assert telemetry.sweep(world, NOW + 45_001).marked_lost == ["bus_01"]


# ============================ 10: atualização inválida não restaura conexão
def test_atualizacao_invalida_nao_restaura_conexao(db, world):
    send(db, world)
    telemetry.sweep(world, NOW + 50_000)
    lost = node(world)
    assert lost["connection_status"] == "connection_lost"
    attempts = [
        dict(uid="m1", data=payload(lat=999)),                    # dado inválido
        dict(uid="m1", data=payload(captured_at=NOW)),            # fix atrasado
        dict(uid="m1", data=payload(is_online=True)),             # tentativa de forjar
        dict(uid="m2", data=payload()),                           # não autorizado
    ]
    for kw in attempts:
        with pytest.raises(TelemetryError):
            send(db, world, now=NOW + 50_000, **kw)
    assert node(world) == lost  # is_online=False e updated_at antigo intactos


# ============================================== 11: autorização do motorista
DENIED = [
    ("passageiro", "m1", PASSAGEIRO, "bus_01", "not_a_driver"),
    ("dono_frota", "m1", DONO_FROTA, "bus_01", "not_a_driver"),
    ("sem_claim", "m1", {}, "bus_01", "missing_role_claim"),
    ("claims_none", "m1", None, "bus_01", "missing_role_claim"),
    ("role_invalida", "m1", {"role": "admin"}, "bus_01", "invalid_role"),
    ("nao_autenticado", None, MOTORISTA, "bus_01", "unauthenticated"),
    ("outro_onibus", "m2", MOTORISTA, "bus_01", "not_active_driver"),
    ("motorista_inativo", "m3", MOTORISTA, "bus_03", "driver_inactive"),
    ("onibus_de_outra_frota", "m1", MOTORISTA, "bus_b", "bus_other_fleet"),
    ("onibus_inexistente", "m1", MOTORISTA, "bus_99", "bus_not_found"),
    ("sem_cadastro_driver", "ghost", MOTORISTA, "bus_01", "not_active_driver"),
]


@pytest.mark.parametrize("uid,claims,bus,reason",
                         [d[1:] for d in DENIED], ids=[d[0] for d in DENIED])
def test_envio_nao_autorizado_e_recusado(db, world, uid, claims, bus, reason):
    with pytest.raises(TelemetryError) as ei:
        send(db, world, uid=uid, data=payload(bus), claims=claims)
    assert ei.value.reason == reason
    assert world.get() is None


def test_fim_de_viagem_remove_no_e_nao_vira_connection_lost(db, world):
    send(db, world)
    with pytest.raises(TelemetryError) as ei:  # outro motorista não encerra
        telemetry.handle_end_telemetry(db, world, "m2", {"busId": "bus_01"}, MOTORISTA)
    assert ei.value.reason == "not_active_driver" and node(world) is not None
    out = telemetry.handle_end_telemetry(db, world, "m1", {"busId": "bus_01"}, MOTORISTA)
    assert out["removed"] is True and node(world) is None
    res = telemetry.sweep(world, NOW + 600_000)
    assert res.marked_lost == [] and world.get() is None


def test_monitor_remove_no_de_onibus_sem_motorista_ativo(db, world):
    send(db, world)
    db.collection("buses").document("bus_01").update({"active_driver_id": None})
    checker = telemetry.firestore_in_service_checker(db)
    res = telemetry.sweep(world, NOW + 60_000, checker)
    assert res.removed == ["bus_01"] and res.marked_lost == []
    assert node(world) is None


def test_monitor_marca_perda_se_onibus_segue_em_servico(db, world):
    send(db, world)
    checker = telemetry.firestore_in_service_checker(db)
    res = telemetry.sweep(world, NOW + 60_000, checker)
    assert res.marked_lost == ["bus_01"] and res.removed == []


# ======================================= 12: chegada simultânea ao monitoramento
def test_atualizacao_chega_durante_a_verificacao_do_monitor(db, world):
    send(db, world)
    late = NOW + 50_000  # nó está "velho" na leitura do monitor...

    def arrives():  # ...mas uma atualização entra ENTRE a leitura e a escrita
        send(db, world, data=payload(lat=-4.0), now=late)

    outcome = telemetry.expire_node(world, "bus_01", late, _after_read=arrives)
    assert outcome == "fresh"  # CAS falhou, releu e viu dado novo: não escreveu
    n = node(world)
    assert n["is_online"] is True and n["connection_status"] == "online"
    assert n["lat"] == -4.0 and n["updated_at"] == late


def test_recuperacao_durante_a_verificacao_vence_o_monitor(db, world):
    send(db, world)
    telemetry.sweep(world, NOW + 50_000)  # já em connection_lost
    late = NOW + 70_000

    def arrives():
        send(db, world, data=payload(lat=-4.5), now=late)

    # O monitor leu o nó (lost + velho) e decide sem escrever; mesmo assim, a
    # recuperação que entrou no meio NÃO pode ser desfeita.
    assert telemetry.expire_node(world, "bus_01", late, _after_read=arrives) == "unchanged"
    n = node(world)
    assert n["is_online"] is True and n["connection_status"] == "online"
    assert n["lat"] == -4.5 and n["updated_at"] == late


def test_varredura_com_relogio_atrasado_nao_rebaixa_telemetria_recente(db, world):
    send(db, world, now=NOW + 100_000)
    res = telemetry.sweep(world, NOW + 50_000)  # "agora" anterior ao updated_at
    assert res.marked_lost == [] and node(world)["is_online"] is True


# ============================ 13: monitoramento independe do aplicativo cliente
def _node(updated_at, online=True):
    return {"lat": -3.6, "lng": -45.3, "speed": 10, "heading": 1,
            "status": "in_service", "updated_at": updated_at,
            "captured_at": updated_at, "is_online": online,
            "connection_status": "online" if online else "connection_lost"}


def test_varios_veiculos_simultaneos(db, root):
    fresh = {}
    for i in range(10):
        stale = i % 2 == 0
        n = _node(NOW if stale else NOW + 40_000)
        root.child(f"b{i}").set(n)
        if not stale:
            fresh[f"b{i}"] = n
    res = telemetry.sweep(root, NOW + 50_000)
    assert sorted(res.marked_lost) == [f"b{i}" for i in range(0, 10, 2)]
    assert res.errors == []
    for bus_id, n in fresh.items():
        assert root.child(bus_id).get() == n  # os recentes não foram tocados


def test_falha_em_um_veiculo_nao_para_os_demais(db, root):
    for b in ("a", "x", "z"):
        root.child(b).set(_node(NOW))

    def in_service(bus_id):
        if bus_id == "x":
            raise RuntimeError("Firestore indisponível")
        return True

    res = telemetry.sweep(root, NOW + 60_000, in_service)
    assert sorted(res.marked_lost) == ["a", "z"]
    assert [b for b, _ in res.errors] == ["x"]
    assert root.child("x").get()["is_online"] is True  # sem decisão: nada muda


def test_no_sem_updated_at_valido_nao_fica_online(db, root):
    root.child("corrompido").set({"lat": -3.6, "is_online": True,
                                  "connection_status": "online"})
    res = telemetry.sweep(root, NOW)
    assert res.marked_lost == ["corrompido"]


def test_loop_do_monitor_funciona_sem_nenhuma_consulta_do_app(db, world):
    """Nenhum cliente lê /telemetry: o processo sozinho detecta as quedas."""
    send(db, world, uid="m1", data=payload("bus_01"), now=NOW)
    send(db, world, uid="m2", data=payload("bus_02"), now=NOW + 40_000)
    clock = iter([NOW + 46_000, NOW + 86_000])  # bus_01 cai; depois bus_02 cai
    results = []
    telemetry.run_sweeps(world, iterations=2, interval_s=5,
                         clock_ms=lambda: next(clock), sleep=lambda s: None,
                         on_result=results.append)
    assert [r.marked_lost for r in results] == [["bus_01"], ["bus_02"]]
    assert node(world, "bus_01")["connection_status"] == "connection_lost"
    assert node(world, "bus_02")["connection_status"] == "connection_lost"


@pytest.mark.skipif(not SUBPROCESS_OK, reason="sem processo filho neste backend")
def test_processo_monitor_real_marca_a_perda(db, world):
    """Executa scripts/telemetry_monitor.py de verdade (relógio real)."""
    now = telemetry.now_ms()
    world.child("bus_01").set(_node(now - 120_000))  # celular sumiu há 2 min
    world.child("bus_02").set(_node(now - 5_000))    # saudável
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "scripts", "telemetry_monitor.py")
    proc = subprocess.run([sys.executable, script, "--once", "--project", PROJECT],
                          capture_output=True, text=True, timeout=90)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert node(world, "bus_01")["connection_status"] == "connection_lost"
    assert node(world, "bus_01")["is_online"] is False
    assert node(world, "bus_02")["connection_status"] == "online"
