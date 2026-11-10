import secrets

from fastapi.testclient import TestClient

import test_fluxo_endpoint as api


client = TestClient(api.app)

_gerador_original_teste = api.generate_random_code

OWNER_ID = "qdz7Km0LMEiCXbzfHsXXgEsXFWhq"


def codigo_disponivel():
    """Gera um ID de seis caracteres que não existe no emulador."""
    while True:
        codigo = secrets.token_hex(3).upper()

        if not (
            api.db.collection("invite_codes")
            .document(codigo)
            .get()
            .exists
        ):
            return codigo


def test_colisao_nao_sobrescreve_convite():
    # Criar um proprietário fictício para este teste.
    # O conftest.py limpa o Firestore antes de cada teste.
    owner_ref = api.db.collection("users").document(
        "teste_owner_colisao_convite"
    )

    owner_ref.set({
        "fleet_owner_id": OWNER_ID,
        "role": "dono_frota",
        "name": "Proprietário de teste",
        "email": "owner-colisao@example.test"
    })

    proprietarios = (
        api.db.collection("users")
        .where("fleet_owner_id", "==", OWNER_ID)
        .where("role", "==", "dono_frota")
        .limit(1)
        .get()
    )

    assert proprietarios, (
        "Não foi possível criar o proprietário de teste."
    )



    # Criar dois códigos exclusivos para este teste
    codigo_existente = codigo_disponivel()
    novo_codigo = codigo_disponivel()

    while novo_codigo == codigo_existente:
        novo_codigo = codigo_disponivel()

    ref_antiga = (
        api.db.collection("invite_codes")
        .document(codigo_existente)
    )

    ref_nova = (
        api.db.collection("invite_codes")
        .document(novo_codigo)
    )

    documento_original = {
        "code": codigo_existente,
        "fleet_owner_id": "PROPRIETARIO_ORIGINAL",
        "used": True,
        "marcador_teste": "NAO_MODIFICAR",
    }

    try:
        # Criar um convite anterior que deve permanecer intacto
        ref_antiga.create(documento_original)

        # Simular: primeiro código colide; segundo código é novo
        codigos = iter([codigo_existente, novo_codigo])
        chamadas = []

        def gerador_simulado():
            codigo = next(codigos)
            chamadas.append(codigo)
            return codigo

        api.generate_random_code = gerador_simulado

        resposta = client.post(
            "/generate-invite",
            json={"fleet_owner_id": OWNER_ID},
        )

        assert resposta.status_code == 200, resposta.text

        dados_resposta = resposta.json()

        # A API deve devolver o segundo código
        assert dados_resposta["invite_code"] == novo_codigo

        # Deve ter tentado exatamente os dois códigos
        assert chamadas == [codigo_existente, novo_codigo]

        # O documento antigo deve continuar exatamente igual
        documento_atual = ref_antiga.get().to_dict()
        assert documento_atual == documento_original

        # O convite novo deve existir separadamente
        documento_novo = ref_nova.get().to_dict()

        assert documento_novo["code"] == novo_codigo
        assert documento_novo["fleet_owner_id"] == OWNER_ID
        assert documento_novo["used"] is False

    finally:
        # Restaurar a função original e remover somente os
        # documentos temporários criados por este teste.
        api.generate_random_code = _gerador_original_teste
        ref_antiga.delete()
        ref_nova.delete()
        owner_ref.delete()