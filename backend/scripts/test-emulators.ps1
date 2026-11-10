# Roda os testes dentro dos emuladores (projeto loirinha-1a25f; nada de produção).
#   .\scripts\test-emulators.ps1          -> lógica + regras (Firestore Emulator)
#   .\scripts\test-emulators.ps1 -E2E     -> inclui chamada real à Function (Auth+Functions)
param([switch]$E2E)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root "functions\venv\Scripts\python.exe"
& $py -m pip install -q -r functions/requirements-dev.txt
if ($E2E) {
  $env:CHECKIN_E2E = "1"
  # O Functions Emulator espera 10 s pelo carregamento do Python; no Windows (1a vez,
  # antivirus) pode demorar mais. Sobe o limite para 90 s.
  $env:FUNCTIONS_DISCOVERY_TIMEOUT = "90"
  firebase emulators:exec --only "firestore,auth,functions" --project loirinha-1a25f "`"$py`" -m pytest functions/tests -v --ignore=functions/tests/fluxo"
} else {
  firebase emulators:exec --only firestore --project loirinha-1a25f "`"$py`" -m pytest functions/tests -v --ignore=functions/tests/fluxo --ignore=functions/tests/test_e2e_callable.py"
}
exit $LASTEXITCODE
