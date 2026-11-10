import os
import firebase_admin
from firebase_admin import db

PROJECT = "loirinha-1a25f"
HOST = "127.0.0.1:9000"

# Garante que o acesso seja feito somente ao emulador local.
os.environ["FIREBASE_DATABASE_EMULATOR_HOST"] = HOST

APP_NAME = "diagnostico-namespace"
DATABASE_URL = f"https://{PROJECT}-default-rtdb.firebaseio.com"

try:
    app = firebase_admin.get_app(APP_NAME)
except ValueError:
    app = firebase_admin.initialize_app(
        options={
            "projectId": PROJECT,
            "databaseURL": DATABASE_URL,
        },
        name=APP_NAME,
    )

root = db.reference("/telemetry", app=app)

print("Dados em /telemetry:")
print(root.get())

print("\nDados em /telemetry/bus1:")
print(root.child("bus1").get())
