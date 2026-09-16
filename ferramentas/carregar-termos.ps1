# Carrega no ATLAS os termos do IBAMA lavrados na mesma fiscalizacao do auto:
# embargo, apreensao, suspensao e demolicao.
#
# O arquivo de origem e o recorte de dados_ibama_termos\termos.json, extraido
# de mais de 320 MB de arquivos publicos (so o de embargo tem 197 MB e 116.057
# linhas), filtrando pelos autos da carteira e descartando termos CANCELADOS.
# A senha e lida do .env e nunca aparece na tela.

$envp = "$env:USERPROFILE\ATLAS-IA\frontend\.env"
$token = ((Get-Content $envp | Where-Object { $_ -match "^VITE_ATLAS_API_TOKEN=" }) -replace "^VITE_ATLAS_API_TOKEN=", "").Trim()
$H = @{ Authorization = ("Bearer " + $token); "Content-Type" = "application/json" }
$url = "https://atlas-geo.onrender.com/api/termos/carregar"

$dados = Get-Content "$env:USERPROFILE\ATLAS-IA\dados_ibama_termos\termos.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$todos = $dados.termos
Write-Host ("termos a carregar: " + $todos.Count)

$lote = 300
$total = 0
for ($i = 0; $i -lt $todos.Count; $i += $lote) {
  $fim = [Math]::Min($i + $lote - 1, $todos.Count - 1)
  $corpo = @{ termos = $todos[$i..$fim] } | ConvertTo-Json -Depth 6 -Compress
  try {
    $r = Invoke-RestMethod -Method Post -Uri $url -Headers $H -Body ([Text.Encoding]::UTF8.GetBytes($corpo)) -TimeoutSec 300
    $total = $r.total_na_base
    Write-Host ("  lote " + ($i/$lote + 1) + ": linhas " + $r.linhas_recebidas + "  |  total na base " + $total)
  } catch {
    Write-Host ("  FALHOU no lote " + ($i/$lote + 1) + ": " + $_.Exception.Message) -ForegroundColor Red
    break
  }
}
Write-Host ""
Write-Host ("concluido. total na base: " + $total) -ForegroundColor Green
Write-Host "Obs: o arquivo publico repete 6 numeros de termo (mesmo termo publicado" -ForegroundColor DarkGray
Write-Host "duas vezes), por isso o total na base fica 6 abaixo das linhas enviadas." -ForegroundColor DarkGray
