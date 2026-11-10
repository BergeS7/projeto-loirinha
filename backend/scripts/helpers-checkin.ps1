# Funcoes auxiliares para testar a Cloud Function checkIn manualmente,
# SOMENTE contra os Firebase Emulators locais (projeto loirinha-1a25f (somente emuladores)).
#
# Uso (a partir da raiz do projeto, em cada nova sessao do PowerShell):
#   . .\scripts\helpers-checkin.ps1          # note o ponto e o espaco antes do caminho
#
#   $t1 = Get-IdToken "motorista1@example.test"
#   Invoke-CheckIn $t1 "TAG-BUS-01"          # check-in como motorista1
#   Invoke-CheckIn $null "TAG-BUS-01"        # chamada sem login (espera 401)
#   Show-TokenClaims $t1                     # mostra a claim `role` do token
#
# A role OFICIAL vem da custom claim `role` do token. Depois de mudar a role
# (scripts\seed_and_call.py set-role ...), chame Get-IdToken de novo: tokens
# antigos continuam com a role antiga.
#
# Requer os emuladores de Auth (9099), Firestore (8080) e Functions (5001) ativos.

$auth  = "http://127.0.0.1:9099/identitytoolkit.googleapis.com/v1"
$fn    = "http://127.0.0.1:5001/loirinha-1a25f/southamerica-east1/checkIn"
$senha = "senha-ficticia-123"

function Get-IdToken($email) {
  $b = @{ email=$email; password=$senha; returnSecureToken=$true } | ConvertTo-Json
  (Invoke-RestMethod -Method Post -Uri "$auth/accounts:signInWithPassword?key=fake" -ContentType "application/json" -Body $b).idToken
}

function Invoke-CheckIn($token, $tag) {
  $h = @{}
  if ($token) { $h["Authorization"] = "Bearer $token" }
  $b = @{ data = @{ tagCode = $tag } } | ConvertTo-Json -Depth 5
  try {
    $r = Invoke-RestMethod -Method Post -Uri $fn -ContentType "application/json" -Headers $h -Body $b
    "HTTP 200"; $r | ConvertTo-Json -Depth 5
  } catch {
    "HTTP $([int]$_.Exception.Response.StatusCode)"; $_.ErrorDetails.Message
  }
}

function Show-TokenClaims($token) {
  $p = $token.Split(".")[1].Replace("-", "+").Replace("_", "/")
  $p = $p.PadRight($p.Length + (4 - $p.Length % 4) % 4, "=")
  $j = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($p)) | ConvertFrom-Json
  "role no token: $($j.role)"
  $j
}
