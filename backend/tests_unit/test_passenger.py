"""Regressões puras: catálogo, ETA e exclusões concorrentes, sem banco ou credenciais.

Execute: functions/venv/Scripts/python.exe -m unittest discover -s tests_unit -v
"""

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions"))
import passenger
import telemetry


def catalog():
    """Percurso aberto de ~1,1 km; seus dados são somente fixtures de teste."""
    return {
        "lines": [
            {
                "id": "l1",
                "numero": "1",
                "nome": "Teste",
                "cor": "#123456",
                "pontoIds": ["p1", "p2"],
                "operacao": "06–20",
                "intervalo": "20 min",
                "tracado": [[0, 1], [0, 1.01]],
                "circular": False,
            }
        ],
        "stops": [
            {"id": "p1", "nome": "Início", "referencia": "Rua A", "lat": 0, "lng": 1},
            {"id": "p2", "nome": "Fim", "referencia": "Rua B", "lat": 0, "lng": 1.01},
        ],
        "buses": [{"id": "bus1", "prefixo": "001", "linhaId": "l1", "sentido": "Fim"}],
        "notices": [],
    }


class PassengerTests(unittest.TestCase):
    """Casos de domínio que não podem inventar previsões ou expor dados internos."""

    def test_catalog_calculates_stop_fractions_without_mutating_input(self):
        raw = catalog()
        validated = passenger.validate_catalog(raw)
        self.assertEqual(validated["lines"][0]["pontoFracoes"], [0, 1])
        self.assertNotIn("pontoFracoes", raw["lines"][0])

    def test_unknown_private_fields_are_rejected(self):
        raw = catalog()
        raw["buses"][0]["active_driver_id"] = "private"
        with self.assertRaises(ValueError):
            passenger.validate_catalog(raw)

    def test_circular_repeated_stop_represents_end_of_trip(self):
        """A última ocorrência da parada inicial deve ter fração 1, e não zero."""
        raw = catalog()
        raw["lines"][0].update(
            circular=True,
            tracado=[[0, 1], [0.01, 1], [0, 1]],
            pontoIds=["p1", "p2", "p1"],
        )
        raw["stops"][1].update(lat=0.01, lng=1)
        line = passenger.validate_catalog(raw)["lines"][0]
        self.assertEqual(line["pontoFracoes"], [0, 0.5, 1])

    def test_open_geometry_cannot_be_published_as_circular(self):
        """A linha não pode dar uma volta fictícia entre extremos distantes."""
        raw = catalog()
        raw["lines"][0]["circular"] = True
        with self.assertRaises(ValueError):
            passenger.validate_catalog(raw)

    def test_invalid_gps_reference_and_duplicate_are_rejected(self):
        for mutate in (
            lambda c: c["stops"][0].update(lat=float("nan")),
            lambda c: c["buses"][0].update(linhaId="missing"),
            lambda c: c["stops"].append(copy.deepcopy(c["stops"][0])),
        ):
            raw = catalog()
            mutate(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                passenger.validate_catalog(raw)

    def test_open_route_does_not_wrap_to_passed_stop(self):
        line = passenger.validate_catalog(catalog())["lines"][0]
        fix = {"lat": 0, "lng": 1.005, "speed": 36, "status": "in_service"}
        result = passenger.projection(line, fix)
        self.assertAlmostEqual(result["progresso"], 0.5)
        self.assertEqual(result["proximoPontoId"], "p2")
        self.assertNotIn("p1", result["previsoes"])
        self.assertEqual(result["minutosProximoPonto"], 1)

    def test_stopped_or_off_route_vehicle_has_no_eta(self):
        line = passenger.validate_catalog(catalog())["lines"][0]
        for lat, speed, status in (
            (0, 0, "in_service"),
            (1, 36, "in_service"),
            (0, 36, "out_of_route"),
        ):
            with self.subTest(lat=lat, speed=speed, status=status):
                result = passenger.projection(
                    line, {"lat": lat, "lng": 1.005, "speed": speed, "status": status}
                )
                self.assertEqual(result["previsoes"], {})
                self.assertIsNone(result["minutosProximoPonto"])


class Reference:
    """Double CAS com versão: simula exatamente a disputa entre leitura e escrita."""

    def __init__(self, value):
        self.value, self.version = value, 1
        self.on_write = None

    def child(self, _):
        return self

    def get(self, etag=False):
        value = copy.deepcopy(self.value)
        return (value, str(self.version)) if etag else value

    def set_if_unchanged(self, expected, value):
        if self.on_write:
            callback, self.on_write = self.on_write, None
            callback()
        if expected != str(self.version):
            return False, self.value, str(self.version)
        self.value = value or None  # RTDB remove objetos vazios.
        self.version += 1
        return True, self.value, str(self.version)


class ConcurrencyTests(unittest.TestCase):
    """O monitor não pode apagar um heartbeat que chegou durante a varredura."""

    def test_monitor_preserves_new_fix_during_removal(self):
        ref = Reference({"updated_at": 1, "is_online": True})

        def heartbeat():
            ref.version += 1
            ref.value = {"updated_at": 100_000, "is_online": True}

        ref.on_write = heartbeat
        outcome = telemetry.expire_node(ref, "bus1", 100_000, lambda _: False)
        self.assertEqual(outcome, "fresh")
        self.assertEqual(ref.value["updated_at"], 100_000)

    def test_checkout_removes_node_conditionally(self):
        ref = Reference({"updated_at": 1})
        with patch.object(telemetry, "authorize_driver"):
            result = telemetry.handle_end_telemetry(
                None, ref, "driver", {"busId": "bus1"}, {"role": "motorista"}
            )
        self.assertTrue(result["removed"])
        self.assertIsNone(ref.value)


if __name__ == "__main__":
    unittest.main()
