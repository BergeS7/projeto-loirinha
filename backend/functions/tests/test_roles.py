"""Testes de roles.py que não dependem de rede (leitura/validação de claims)."""
import pytest

import roles


def test_roles_permitidas_sao_as_tres_do_projeto():
    assert set(roles.ALLOWED_ROLES) == {"dono_frota", "motorista", "passageiro"}
    assert roles.ROLE_CLAIM_KEY == "role"


@pytest.mark.parametrize("role", ["dono_frota", "motorista", "passageiro"])
def test_read_role_valida(role):
    assert roles.read_role({"role": role, "outra": 1}) == (role, None)


@pytest.mark.parametrize("claims", [None, {}, {"x": 1}, {"role": None}, "x", [], 3])
def test_read_role_ausente(claims):
    assert roles.read_role(claims) == (None, "missing")


@pytest.mark.parametrize("role", ["admin", "", "Motorista", 1, True, ["motorista"]])
def test_read_role_invalida(role):
    assert roles.read_role({"role": role}) == (None, "invalid")


@pytest.mark.parametrize("role", ["admin", "", None, 1, "MOTORISTA"])
def test_set_user_role_rejeita_role_invalida_antes_de_qualquer_io(role):
    # Levanta antes de importar/usar o Admin SDK: nada é gravado.
    with pytest.raises(roles.InvalidRoleError):
        roles.set_user_role("qualquer-uid", role)
