r"""Redefine a senha de uma conta no Auth EMULATOR (nunca em produção).

Uso (PowerShell, na pasta backend/, com o Auth Emulator rodando):

  $env:NOVA_SENHA = "<senha de teste>"
  functions\venv\Scripts\python.exe scripts\redefinir_senha_motorista.py [UID]

A senha vem da variável de ambiente NOVA_SENHA, para não ficar no código
versionado (recomendação da documentação do backend, seção 3.3).
"""
import os
import sys

from firebase_admin import auth
from emulator_auth import emulator_admin_app

PROJECT = "loirinha-1a25f"
UID = sys.argv[1] if len(sys.argv) > 1 else "Hszew14NUMvjq8MipIoOgv7oiOSu"
NEW_PASSWORD = os.environ.get("NOVA_SENHA", "")

if len(NEW_PASSWORD) < 6:
    sys.exit("Defina NOVA_SENHA (mínimo de 6 caracteres) antes de rodar o script.")

app = emulator_admin_app(PROJECT)

try:
    # Confirma que a conta já existe no Auth Emulator
    user = auth.get_user(UID, app=app)

    # Altera somente a senha dessa conta
    auth.update_user(
        UID,
        password=NEW_PASSWORD,
        app=app
    )

    print("SENHA REDEFINIDA COM SUCESSO")
    print("UID:", user.uid)
    print("Email:", user.email)

except auth.UserNotFoundError:
    print("ERRO: usuario nao encontrado. Nenhuma conta foi criada.")

except Exception as e:
    print("ERRO:", type(e).__name__, str(e))
