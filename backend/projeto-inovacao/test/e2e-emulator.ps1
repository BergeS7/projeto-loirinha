$ErrorActionPreference = "Stop"

$env:APP_ENV = "emulator"
$env:FIREBASE_PROJECT_ID = "demo-loirinha"
$env:FIREBASE_AUTH_EMULATOR_HOST = "127.0.0.1:9099"

# Cria usuário

$uidNew = node -e "const a=require('firebase-admin');a.initializeApp({projectId:'demo-loirinha'});a.auth().createUser({email:'teste@loirinha.dev'}).then(async u=>{await a.auth().setCustomUserClaims(u.uid,{beta:true});console.log(u.uid)})"


$uidNew = $uidNew.Trim()

Write-Host "UID criado: $uidNew"

$fail = 0

foreach ($role in @("passageiro", "motorista", "dono_frota")) {


node scripts/firebase/set-custom-claim.js $uidNew $role *> $null

if ($LASTEXITCODE -ne 0) {
    Write-Host "FALHA: $role"
    $fail = 1
}

$claims = node scripts/firebase/get-custom-claim.js $uidNew
$claimsCompact = $claims -replace '\s',''

if ($claimsCompact -match "`"role`":`"$role`"") {
    Write-Host "OK  role=$role"
}
else {
    Write-Host "FALHA verificar $role"
    $fail = 1
}

}

$claims = node scripts/firebase/get-custom-claim.js $uidNew

if ($claims -match '"beta"\s*:\s*true') {
Write-Host "OK  claim 'beta' preservado"
}
else {
Write-Host "FALHA: beta perdido"
$fail = 1
}

# Testa role inválida.

# O erro é esperado, portanto não devemos deixar o PowerShell

# interromper o script antes de verificar o resultado.

$oldErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"

$invalidRole = node scripts/firebase/set-custom-claim.js $uidNew admin 2>&1
$invalidRoleExitCode = $LASTEXITCODE

$ErrorActionPreference = $oldErrorActionPreference

$invalidRoleText = ($invalidRole | Out-String)

if (($invalidRoleExitCode -ne 0) -and ($invalidRoleText -match "role")) {
Write-Host "OK  role invalida rejeitada"
}
else {
Write-Host "FALHA role invalida"
$fail = 1
}

# Testa UID inexistente.
# O erro é esperado.

$oldErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"

$invalidUid = & node scripts/firebase/set-custom-claim.js uid-inexistente motorista 2>&1
$invalidUidExitCode = $LASTEXITCODE

$ErrorActionPreference = $oldErrorActionPreference

$invalidUidText = [string]::Join(" ", @($invalidUid))

Write-Host "DEBUG UID - ExitCode: $invalidUidExitCode"
Write-Host "DEBUG UID - Saida: $invalidUidText"

if (($invalidUidExitCode -ne 0) -and ($invalidUidText -match "Firebase Authentication")) {
Write-Host "OK UID inexistente tratado"
}
else {
Write-Host "FALHA uid"
$fail = 1
}

exit $fail
