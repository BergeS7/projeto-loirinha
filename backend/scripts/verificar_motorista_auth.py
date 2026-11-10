from firebase_admin import auth
from emulator_auth import emulator_admin_app

PROJECT = "loirinha-1a25f"
UID = "Hszew14NUMvjq8MipIoOgv7oiOSu"

try:
    app = emulator_admin_app(PROJECT)
    user = auth.get_user(UID, app=app)

    print("USUARIO ENCONTRADO")
    print("UID:", user.uid)
    print("Email:", user.email)
    print("Custom claims:", user.custom_claims)

except auth.UserNotFoundError:
    print("USUARIO NAO ENCONTRADO NO AUTH EMULATOR")

except Exception as e:
    print("ERRO:", type(e).__name__, str(e))
