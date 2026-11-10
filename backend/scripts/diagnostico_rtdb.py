from emulator_rtdb import emulator_telemetry_root

PROJECT = "loirinha-1a25f"

try:
    root = emulator_telemetry_root(PROJECT)

    print("Referencia RTDB criada pelo helper.")
    print("\nConteudo da raiz /telemetry:")
    print(root.get())

    print("\nConteudo de /telemetry/bus1:")
    print(root.child("bus1").get())

except Exception as exc:
    print("ERRO:", type(exc).__name__, str(exc))
