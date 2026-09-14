# Carrega no ATLAS o perfil de divida ativa federal dos autuados PJ.
#
# O arquivo de origem e o agregado da PGFN (dados_pgfn\divida_ativa.json),
# extraido uma vez por trimestre a partir dos 9 GB do arquivo publico.
# A senha e lida do .env e nunca aparece na tela.

$envp = "$env:USERPROFILE\ATLAS-IA\frontend\.env"
$token = ((Get-Content $envp | Where-Object { $_ -match "^VITE_ATLAS_API_TOKEN=" }) -replace "^VITE_ATLAS_API_TOKEN=", "").Trim()
$H = @{ Authorization = ("Bearer " + $token); "Content-Type" = "application/json" }
$url = "https://atlas-geo.onrender.com/api/divida-ativa/carregar"

$dados = Get-Content "$env:USERPROFILE\ATLAS-IA\dados_pgfn\divida_ativa.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$ref = $dados.meta.referencia_da_base
$todos = $dados.devedores
Write-Host ("devedores a carregar: " + $todos.Count + "  (referencia " + $ref + ")")

$lote = 300
$total = 0
for ($i = 0; $i -lt $todos.Count; $i += $lote) {
  $fim = [Math]::Min($i + $lote - 1, $todos.Count - 1)
  $corpo = @{ referencia_da_base = $ref; devedores = $todos[$i..$fim] } | ConvertTo-Json -Depth 6 -Compress
  try {
    $r = Invoke-RestMethod -Method Post -Uri $url -Headers $H -Body ([Text.Encoding]::UTF8.GetBytes($corpo)) -TimeoutSec 300
    $total = $r.total_na_base
    Write-Host ("  lote " + ($i/$lote + 1) + ": gravados " + $r.gravados + "  |  total na base " + $total)
  } catch {
    Write-Host ("  FALHOU no lote " + ($i/$lote + 1) + ": " + $_.Exception.Message) -ForegroundColor Red
    break
  }
}
Write-Host ""
Write-Host ("concluido. total na base: " + $total) -ForegroundColor Green
