
# Inicia os emuladores locais e importa/exporta os dados.
Set-Location (Split-Path -Parent $PSScriptRoot)

$exportDir = Join-Path (Get-Location) "emulator-data"

firebase emulators:start `
  --only "firestore,auth,functions,database" `
  --project loirinha-1a25f `
  --import $exportDir `
  --export-on-exit $exportDir
