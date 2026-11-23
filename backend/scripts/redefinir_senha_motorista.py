from firebase_admin import auth
from emulator_auth import emulator_admin_app

PROJECT = "loirinha-1a25f"
UID = "Hszew14NUMvjq8MipIoOgv7oiOSu"
NEW_PASSWORD = "TesteTelemetria#2026"

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
    print("Nova senha de teste:", NEW_PASSWORD)

except auth.UserNotFoundError:
    print("ERRO: usuario nao encontrado. Nenhuma conta foi criada.")

except Exception as e:
    print("ERRO:", type(e).__name__, str(e))
