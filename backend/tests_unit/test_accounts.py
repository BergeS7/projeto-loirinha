"""Autorização e compensação de contas, sem Auth/Firestore reais."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions"))
import accounts
from fleet_routes import RouteError


class AccountTests(unittest.TestCase):
    """Tokens e frota são conferidos no backend, independentemente da interface."""

    def test_passenger_cannot_list_or_create_drivers(self):
        for handler in (
            accounts.list_users,
            accounts.create_driver,
            accounts.list_routes,
            accounts.set_active,
        ):
            with self.subTest(handler=handler.__name__), self.assertRaises(RouteError):
                handler(MagicMock(), "passenger", {}, {"role": "passageiro"})

    def test_unauthenticated_cannot_register(self):
        with self.assertRaises(RouteError):
            accounts.register_passenger(MagicMock(), None, {"name": "Teste"}, {})

    def test_public_registration_rejects_role_payload(self):
        with self.assertRaises(RouteError):
            accounts.register_passenger(
                MagicMock(), "p1", {"name": "Teste", "role": "dono_frota"}, {}
            )

    def test_existing_owner_cannot_be_rewritten_as_passenger(self):
        record = SimpleNamespace(
            custom_claims={"role": "dono_frota"}, email="a@example.test"
        )
        with (
            patch.object(accounts.auth, "get_user", return_value=record),
            self.assertRaises(RouteError),
        ):
            accounts.register_passenger(MagicMock(), "owner", {"name": "Teste"}, {})

    def test_passenger_claim_preserves_other_claims(self):
        db = MagicMock()
        db.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {}
        record = SimpleNamespace(custom_claims={"custom": True}, email="p@example.test")
        with (
            patch.object(accounts.auth, "get_user", return_value=record),
            patch.object(accounts.auth, "set_custom_user_claims") as claims,
        ):
            accounts.register_passenger(db, "p1", {"name": "Passageiro"}, {})
        claims.assert_called_once_with("p1", {"custom": True, "role": "passageiro"})

    def test_driver_creation_compensates_failed_database_commit(self):
        db = MagicMock()
        db.batch.return_value.commit.side_effect = RuntimeError("database unavailable")
        with (
            patch.object(accounts, "owner", return_value="owner"),
            patch.object(
                accounts.auth, "create_user", return_value=SimpleNamespace(uid="new")
            ),
            patch.object(accounts.auth, "set_custom_user_claims"),
            patch.object(accounts.auth, "delete_user") as delete,
        ):
            with self.assertRaises(RuntimeError):
                accounts.create_driver(
                    db,
                    "owner",
                    {"name": "Motorista", "email": "m@example.test"},
                    {"role": "dono_frota"},
                )
        delete.assert_called_once_with("new")

    def test_cannot_change_driver_of_other_fleet(self):
        db = MagicMock()
        reference = db.collection.return_value.document.return_value
        reference.get.return_value.to_dict.return_value = {"fleet_owner_id": "other"}
        with (
            patch.object(accounts, "owner", return_value="owner"),
            self.assertRaises(RouteError),
        ):
            accounts.set_active(db, "owner", {"driverId": "m1", "active": False}, {})
        reference.update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
