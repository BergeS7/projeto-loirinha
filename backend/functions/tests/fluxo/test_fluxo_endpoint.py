import os
import random
import string

from google.api_core.exceptions import AlreadyExists

from fastapi import FastAPI, HTTPException

from pydantic import BaseModel, field_validator

# Configuração do emulador
os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
os.environ["GCLOUD_PROJECT"] = "loirinha-1a25f"

import firebase_admin
from firebase_admin import credentials, firestore

# Inicialização do Firebase
class FakeCredential(credentials.Base):
    def get_credential(self):
        return None

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(
        FakeCredential(),
        options={"projectId": "loirinha-1a25f"}
    )

db = firestore.client()

# Criação da aplicação FastAPI
app = FastAPI()



class InviteRequest(BaseModel):
    fleet_owner_id: str

    @field_validator("fleet_owner_id")
    @classmethod
    def validar_fleet_owner_id(cls, valor: str) -> str:
        valor = valor.strip()

        if not valor:
            raise ValueError("fleet_owner_id não pode ser vazio ou conter apenas espaços")

        return valor

def generate_random_code(length=6):
    letters_and_digits = string.ascii_uppercase + string.digits
    return ''.join(random.choice(letters_and_digits) for _ in range(length))



@app.post("/generate-invite")
async def generate_invite(req: InviteRequest):
    # 1. Procurar o proprietário na coleção users
    proprietarios = (
        db.collection("users")
        .where("fleet_owner_id", "==", req.fleet_owner_id)
        .where("role", "==", "dono_frota")
        .limit(1)
        .get()
    )

    # 2. Rejeitar se não existir um proprietário válido
    if not proprietarios:
        raise HTTPException(
            status_code=404,
            detail="Proprietário de frota não encontrado"
        )

    # 3. Gerar o código somente após validar o proprietário
        # Tentar gerar e salvar um código que ainda não exista
    for _ in range(10):
        new_code = generate_random_code()

        doc_ref = db.collection("invite_codes").document(new_code)

        try:
            doc_ref.create({
                "code": new_code,
                "fleet_owner_id": req.fleet_owner_id,
                "used": False,
                "created_at": firestore.SERVER_TIMESTAMP
            })
            break

        except AlreadyExists:
            # O código já existe; tentar gerar outro
            continue
    else:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível gerar um código de convite exclusivo"
        )

    # 4. Salvar o convite no Firestore Emulator
    doc_ref = db.collection("invite_codes").document(new_code)
    doc_ref.set({
        "code": new_code,
        "fleet_owner_id": req.fleet_owner_id,
        "used": False,
        "created_at": firestore.SERVER_TIMESTAMP
    })
    return {
        "status": "success",
        "invite_code": new_code,
        "fleet_owner_id": req.fleet_owner_id
    }
