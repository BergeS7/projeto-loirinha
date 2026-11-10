from emulator_rtdb import emulator_firestore_client

PROJECT = "loirinha-1a25f"
UID = "Hszew14NUMvjq8MipIoOgv7oiOSu"
BUS_ID = "bus1"

db = emulator_firestore_client(PROJECT)

print("=== ONIBUS ===")
bus_ref = db.collection("buses").document(BUS_ID)
bus_doc = bus_ref.get()

if not bus_doc.exists:
    print("Onibus nao encontrado.")
else:
    bus = bus_doc.to_dict()
    print("ID:", BUS_ID)
    print("Motorista ativo:", bus.get("active_driver_id"))
    print("Dono da frota:", bus.get("fleet_owner_id"))

print("\n=== MOTORISTA ===")
drivers = db.collection("drivers").where(
    "user_id", "==", UID
).stream()

found = False
for doc in drivers:
    found = True
    print("Documento:", doc.id)
    print("Dados:", doc.to_dict())

if not found:
    print("Nenhum documento encontrado para esse UID.")
