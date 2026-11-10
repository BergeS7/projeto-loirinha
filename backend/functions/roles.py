"""Roles do sistema, armazenadas como Custom Claim `role` no Firebase Auth.

FONTE OFICIAL DA ROLE = custom claim `role` do ID token. O campo
`users/{uid}.role` do Firestore (se existir) é apenas informativo/legado:
alterá-lo NÃO concede nem remove permissão.

Mesma convenção do `projeto-inovacao` (claim `{"role": "<papel>"}` e as três
roles abaixo). Se adicionar uma role, inclua-a em ALLOWED_ROLES.

Este módulo não faz I/O por padrão: `read_role` é puro (usado pela Function) e
`set_user_role` só é chamado por seeds/testes/ferramentas administrativas.
"""

from __future__ import annotations

from typing import Any

ROLE_CLAIM_KEY = "role"
ROLE_DONO_FROTA = "dono_frota"
ROLE_MOTORISTA = "motorista"
ROLE_PASSAGEIRO = "passageiro"
ALLOWED_ROLES = (ROLE_DONO_FROTA, ROLE_MOTORISTA, ROLE_PASSAGEIRO)


class InvalidRoleError(ValueError):
    """Role fora de ALLOWED_ROLES ao tentar gravar uma claim."""

    def __init__(self, role: Any):
        super().__init__(
            f"role inválida ({role!r}). Permitidas: {', '.join(ALLOWED_ROLES)}")


def is_valid_role(role: Any) -> bool:
    return isinstance(role, str) and role in ALLOWED_ROLES


def read_role(claims: Any) -> tuple[str | None, str | None]:
    """Lê a role das claims do token verificado.

    Devolve (role, problema): problema é None se a role é válida; senão
    "missing" (claim ausente) ou "invalid" (presente, mas fora da lista).
    Fail-closed: `claims` que não seja dict equivale a claim ausente.
    """
    if not isinstance(claims, dict):
        return None, "missing"
    raw = claims.get(ROLE_CLAIM_KEY)
    if raw is None:
        return None, "missing"
    if not is_valid_role(raw):
        return None, "invalid"
    return raw, None


def set_user_role(uid: str, role: str, app=None) -> dict:
    """Define a claim `role` PRESERVANDO as demais claims do usuário.

    `set_custom_user_claims` substitui o objeto inteiro; por isso lemos as
    claims atuais, alteramos só `role` e gravamos o conjunto. Idempotente.
    Usa o Admin SDK (`firebase_admin.auth`); o chamador é responsável por
    apontá-lo ao Auth Emulator (veja scripts/emulator_auth.py).

    Retorna {"uid", "previous_role", "role", "claims"}.
    """
    if not is_valid_role(role):
        raise InvalidRoleError(role)
    from firebase_admin import auth  # import tardio: a Function não precisa

    user = auth.get_user(uid, app=app)  # levanta UserNotFoundError se não existe
    claims = dict(user.custom_claims or {})
    previous = claims.get(ROLE_CLAIM_KEY)
    claims[ROLE_CLAIM_KEY] = role
    auth.set_custom_user_claims(uid, claims, app=app)
    return {"uid": uid, "previous_role": previous, "role": role, "claims": claims}
