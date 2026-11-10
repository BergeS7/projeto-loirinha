from emulator_rtdb import emulator_telemetry_root

PROJECT = "loirinha-1a25f"
BUS_ID = "bus1"

try:
    root = emulator_telemetry_root(PROJECT)
    data = root.child(BUS_ID).get()

    if data is None:
        print("Nenhuma telemetria encontrada em /telemetry/" + BUS_ID)
    else:
        print("TELEMETRIA ENCONTRADA:")
        print(data)

except Exception as exc:
    print("ERRO:", type(exc).__name__, str(exc))
