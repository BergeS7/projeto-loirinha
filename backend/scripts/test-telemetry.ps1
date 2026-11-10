# Testes da telemetria/heartbeat dentro dos emuladores Firestore + Realtime Database
# (projeto loirinha-1a25f; nada de produção). Nao usa Auth/Functions Emulator.
#   .\scripts\test-telemetry.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root "functions\venv\Scripts\python.exe"
& $py -m pip install -q -r functions/requirements-dev.txt
firebase emulators:exec --only "firestore,database" --project loirinha-1a25f "`"$py`" -m pytest functions/tests/test_telemetry.py functions/tests/test_telemetry_rules.py -v"
exit $LASTEXITCODE
