"""Testes do seed da coleção `routes` (scripts/seed_routes.py).

Rodam dentro do Firestore Emulator (mesma infraestrutura dos demais testes);
usam somente dados fictícios. Os testes de validação não gravam nada.
"""
import copy
import os
import re
import sys

import pytest

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import seed_routes as sr  # noqa: E402

QUIET = lambda *_args, **_kw: None  # noqa: E731 - silencia o log nos testes

# Conteúdo exato pedido para a primeira rota (conferência independente do script).
ROUTE001_ESPERADA = {
    "name": "Centro - Rodoviária",
    "origin": {"name": "Terminal Central", "latitude": -3.668, "longitude": -45.381},
    "destination": {"name": "Terminal Rodoviário",
                    "latitude": -3.674, "longitude": -45.389},
    "stops": [
        {"name": "Praça Central", "latitude": -3.669, "longitude": -45.383, "order": 1},
        {"name": "Hospital", "latitude": -3.671, "longitude": -45.385, "order": 2},
    ],
    "color_hex_route": "#1E88E5",
    "color_hex_out_route": "#FF6D00",
}


def doc(db, route_id):
    return db.collection("routes").document(route_id).get()


def valid_route():
    return copy.deepcopy(sr.ROUTES["route001"])


# ------------------------------------------------------------- validação ----
def test_rotas_do_seed_sao_validas():
    assert set(sr.ROUTES) >= {"route001", "route002"}
    assert sr.validate_routes(sr.ROUTES) == {}


def test_route001_tem_exatamente_os_dados_pedidos():
    assert sr.ROUTES["route001"] == ROUTE001_ESPERADA


def test_route002_estrutura_e_paradas_sem_invencao():
    r = sr.ROUTES["route002"]
    assert set(r) == {"name", "origin", "destination", "stops",
                      "color_hex_route", "color_hex_out_route"}
    assert r["stops"] == []  # sem evidência de paradas oficiais
    for p in (r["origin"], r["destination"]):
        assert set(p) == {"name", "latitude", "longitude"}
        # sede dos municípios fica nesta região do Maranhão (sanidade grosseira)
        assert -4.0 < p["latitude"] < -3.3 and -45.7 < p["longitude"] < -45.1


def _canais(cor):
    return tuple(int(cor[i:i + 2], 16) for i in (1, 3, 5))


@pytest.mark.parametrize("route_id", ["route001", "route002"])
def test_cores_presentes_e_hexadecimais_nas_duas_rotas(route_id):
    r = sr.ROUTES[route_id]
    for campo in ("color_hex_route", "color_hex_out_route"):
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", r[campo]), (campo, r[campo])
    assert r["color_hex_route"].lower() != r["color_hex_out_route"].lower()


@pytest.mark.parametrize("route_id", ["route001", "route002"])
def test_cor_da_rota_e_fria_e_a_do_desvio_e_quente(route_id):
    r = sr.ROUTES[route_id]
    rr, _, rb = _canais(r["color_hex_route"])
    orr, _, orb = _canais(r["color_hex_out_route"])
    assert rb > rr, "cor da rota deveria ser fria (mais azul que vermelho)"
    assert orr > orb, "cor do desvio deveria ser quente (mais vermelho que azul)"


def test_limites_validos_e_stops_vazio():
    r = valid_route()
    r["origin"].update(latitude=90, longitude=-180)
    r["destination"].update(latitude=-90, longitude=180)
    r["stops"] = []
    assert sr.validate_route("route_x", r) == []


def _set(path, value):
    def mutate(r):
        target = r
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    return mutate


def _delete(path):
    def mutate(r):
        target = r
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]
    return mutate


CASOS_INVALIDOS = [
    ("name_vazio", _set(["name"], "   "), "name"),
    ("name_numero", _set(["name"], 123), "name"),
    ("sem_name", _delete(["name"]), "name: ausente"),
    ("sem_origin", _delete(["origin"]), "origin: ausente"),
    ("sem_destination", _delete(["destination"]), "destination: ausente"),
    ("sem_stops", _delete(["stops"]), "stops: ausente"),
    ("origin_sem_latitude", _delete(["origin", "latitude"]), "origin.latitude: ausente"),
    ("origin_sem_longitude", _delete(["origin", "longitude"]), "origin.longitude: ausente"),
    ("origin_sem_name", _delete(["origin", "name"]), "origin.name: ausente"),
    ("destination_lat_alta", _set(["destination", "latitude"], 90.5), "destination.latitude"),
    ("origin_lat_baixa", _set(["origin", "latitude"], -91), "origin.latitude"),
    ("origin_lon_baixa", _set(["origin", "longitude"], -180.1), "origin.longitude"),
    ("destination_lon_alta", _set(["destination", "longitude"], 181), "destination.longitude"),
    ("lat_texto", _set(["origin", "latitude"], "-3.6"), "origin.latitude"),
    ("lat_bool", _set(["origin", "latitude"], True), "origin.latitude"),
    ("lat_nan", _set(["origin", "latitude"], float("nan")), "origin.latitude"),
    ("lon_infinita", _set(["origin", "longitude"], float("inf")), "origin.longitude"),
    ("origin_nao_objeto", _set(["origin"], "Terminal"), "origin"),
    ("stops_nao_lista", _set(["stops"], {"a": 1}), "stops: deve ser uma lista"),
    ("parada_nao_objeto", _set(["stops"], ["Praça"]), "stops[0]"),
    ("parada_sem_order", _delete(["stops", 0, "order"]), "stops[0].order: ausente"),
    ("parada_sem_name", _delete(["stops", 1, "name"]), "stops[1].name: ausente"),
    ("parada_lat_invalida", _set(["stops", 0, "latitude"], 120), "stops[0].latitude"),
    ("order_zero", _set(["stops", 0, "order"], 0), "stops[0].order"),
    ("order_negativa", _set(["stops", 0, "order"], -1), "stops[0].order"),
    ("order_decimal", _set(["stops", 0, "order"], 1.5), "stops[0].order"),
    ("order_bool", _set(["stops", 0, "order"], True), "stops[0].order"),
    ("order_texto", _set(["stops", 0, "order"], "1"), "stops[0].order"),
    ("order_repetida", _set(["stops", 1, "order"], 1), "ordens repetidas"),
    ("sem_color_hex_route", _delete(["color_hex_route"]), "color_hex_route: ausente"),
    ("sem_color_hex_out_route", _delete(["color_hex_out_route"]),
     "color_hex_out_route: ausente"),
    ("cor_rota_nome", _set(["color_hex_route"], "blue"), "color_hex_route"),
    ("cor_rota_sem_cerquilha", _set(["color_hex_route"], "1E88E5"), "color_hex_route"),
    ("cor_rota_curta", _set(["color_hex_route"], "#12345"), "color_hex_route"),
    ("cor_rota_longa", _set(["color_hex_route"], "#1E88E5FF"), "color_hex_route"),
    ("cor_rota_nao_hex", _set(["color_hex_route"], "#GGGGGG"), "color_hex_route"),
    ("cor_rota_vazia", _set(["color_hex_route"], ""), "color_hex_route"),
    ("cor_rota_numero", _set(["color_hex_route"], 123456), "color_hex_route"),
    ("cor_rota_none", _set(["color_hex_route"], None), "color_hex_route"),
    ("cor_desvio_nome", _set(["color_hex_out_route"], "red"), "color_hex_out_route"),
    ("cor_desvio_curta", _set(["color_hex_out_route"], "#FFF"), "color_hex_out_route"),
    ("cor_desvio_espaco", _set(["color_hex_out_route"], "#FF6D00 "), "color_hex_out_route"),
    ("cor_desvio_numero", _set(["color_hex_out_route"], 0xFF6D00), "color_hex_out_route"),
    ("campo_extra_raiz", _set(["id"], "route001"), "id: campo inesperado"),
    ("campo_extra_origin", _set(["origin", "order"], 1), "origin.order: campo inesperado"),
]


@pytest.mark.parametrize("nome,mutacao,trecho", CASOS_INVALIDOS,
                         ids=[c[0] for c in CASOS_INVALIDOS])
def test_dados_invalidos_sao_rejeitados(nome, mutacao, trecho):
    r = valid_route()
    mutacao(r)
    problemas = sr.validate_route("route_x", r)
    assert problemas, f"{nome}: deveria ser inválido"
    assert any(trecho in p for p in problemas), problemas


@pytest.mark.parametrize("route_id", ["", "  ", "a/b", ".", "..", "__id__", None, 5])
def test_id_de_documento_invalido(route_id):
    problemas = sr.validate_route(route_id, valid_route())
    assert any(p.startswith("id:") for p in problemas), problemas


def test_documento_que_nao_e_objeto():
    assert sr.validate_route("route_x", ["x"]) == ["documento: deve ser um objeto"]


# --------------------------------------------------- gravação no emulador ----
def test_grava_as_duas_rotas(db):
    results = sr.seed_routes(db, sr.ROUTES, log=QUIET)
    assert dict(results) == {"route001": "created", "route002": "created"}
    assert doc(db, "route001").to_dict() == ROUTE001_ESPERADA
    assert doc(db, "route002").to_dict() == sr.ROUTES["route002"]


def test_id_nao_e_gravado_como_campo(db):
    sr.seed_routes(db, sr.ROUTES, log=QUIET)
    for rid in ("route001", "route002"):
        assert "id" not in doc(db, rid).to_dict()


def test_rodar_de_novo_atualiza_sem_duplicar(db):
    sr.seed_routes(db, sr.ROUTES, log=QUIET)
    results = sr.seed_routes(db, sr.ROUTES, log=QUIET)
    assert dict(results) == {"route001": "updated", "route002": "updated"}
    ids = sorted(d.id for d in db.collection("routes").stream())
    assert ids == ["route001", "route002"]
    assert doc(db, "route001").to_dict() == ROUTE001_ESPERADA


def test_documento_existente_e_substituido_por_completo(db):
    db.collection("routes").document("route001").set(
        {"name": "Antigo", "campo_manual": 1})
    results = sr.seed_routes(db, sr.ROUTES, log=QUIET)
    assert dict(results)["route001"] == "updated"
    assert doc(db, "route001").to_dict() == ROUTE001_ESPERADA  # sem campo_manual


def test_skip_existing_nao_sobrescreve(db):
    db.collection("routes").document("route001").set({"name": "Meu ajuste"})
    results = sr.seed_routes(db, sr.ROUTES, skip_existing=True, log=QUIET)
    assert dict(results) == {"route001": "skipped", "route002": "created"}
    assert doc(db, "route001").to_dict() == {"name": "Meu ajuste"}
    assert doc(db, "route002").exists


def test_nao_mexe_em_documentos_nao_relacionados(db):
    db.collection("routes").document("outra_rota").set({"name": "Outra"})
    db.collection("buses").document("bus_x").set(
        {"tag_code": "TAG-X", "active_driver_id": None})
    sr.seed_routes(db, sr.ROUTES, log=QUIET)
    assert doc(db, "outra_rota").to_dict() == {"name": "Outra"}
    assert db.collection("buses").document("bus_x").get().to_dict() == {
        "tag_code": "TAG-X", "active_driver_id": None}


def test_rota_invalida_bloqueia_toda_a_gravacao(db):
    ruim = valid_route()
    ruim["origin"]["latitude"] = 999
    with pytest.raises(sr.SeedError) as exc:
        sr.seed_routes(db, {"route001": valid_route(), "route_ruim": ruim},
                       log=QUIET)
    assert exc.value.exit_code == 1
    assert "route_ruim" in exc.value.message and "origin.latitude" in exc.value.message
    assert list(db.collection("routes").stream()) == []  # nem a válida foi gravada


# ------------------------------------------------- ambiente / emulador ----
def test_emulador_indisponivel_da_erro_claro():
    with pytest.raises(sr.SeedError) as exc:
        sr.check_emulator_reachable("127.0.0.1:1", timeout=2)  # porta sem serviço
    assert exc.value.exit_code == 2
    assert "Firestore Emulator" in exc.value.message
    assert "start-emulators.ps1" in exc.value.message


def test_main_sem_emulador_retorna_2(monkeypatch, capsys):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:1")
    assert sr.main([]) == 2
    assert "ERRO" in capsys.readouterr().err


@pytest.mark.parametrize("host", ["firestore.googleapis.com:443", "10.0.0.5:8080",
                                  "8080", "127.0.0.1:abc"])
def test_host_nao_local_ou_invalido_e_recusado(host):
    with pytest.raises(sr.SeedError) as exc:
        sr.resolve_emulator_host({"FIRESTORE_EMULATOR_HOST": host})
    assert exc.value.exit_code == 2


@pytest.mark.parametrize("host", ["127.0.0.1:8080", "localhost:8080", "[::1]:8080"])
def test_hosts_locais_sao_aceitos(host):
    assert sr.resolve_emulator_host({"FIRESTORE_EMULATOR_HOST": host}) == host


def test_host_padrao_quando_variavel_ausente():
    assert sr.resolve_emulator_host({}) == "127.0.0.1:8080"


def test_projeto_que_nao_e_demo_e_recusado():
    with pytest.raises(sr.SeedError):
        sr.check_project_id("meu-projeto-real")
    sr.check_project_id("demo-checkin")  # não levanta
    sr.check_project_id("loirinha-1a25f")  # projeto Loirinha (emulador) também passa


def test_main_dry_run_nao_conecta_nem_grava(monkeypatch, capsys, db):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:1")  # inalcançável
    assert sr.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "DRY-RUN" in out and "route001" in out and "route002" in out
    assert list(db.collection("routes").stream()) == []


def test_main_grava_pelo_cli(db, capsys):
    assert sr.main(["--only", "route002"]) == 0
    out = capsys.readouterr().out
    assert "CREATED" in out and "route002" in out
    ids = [d.id for d in db.collection("routes").stream()]
    assert ids == ["route002"]


def test_main_rota_desconhecida_retorna_1(capsys):
    assert sr.main(["--only", "route999"]) == 1
    assert "route999" in capsys.readouterr().err
