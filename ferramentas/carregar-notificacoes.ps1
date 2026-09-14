# Carrega no ATLAS as notificacoes do IBAMA cujo processo consta da carteira.
#
# O arquivo de origem e o recorte de dados_ibama_notif\notificacoes.json,
# extraido do arquivo publico fiscalizacao_notificacao.csv (113 MB, 439.187
# notificacoes) filtrando apenas os processos que a carteira acompanha.
# A senha e lida do .env e nunca aparece na tela.

$envp = "$env:USERPROFILE\ATLAS-IA\frontend\.env"
$token = ((Get-Content $envp | Where-Object { $_ -match "^VITE_ATLAS_API_TOKEN=" }) -replace "^VITE_ATLAS_API_TOKEN=", "").Trim()
$H = @{ Authorization = ("Bearer " + $token); "Content-Type" = "application/json" }
$url = "https://atlas-geo.onrender.com/api/notificacoes/carregar"

$dados = Get-Content "$env:USERPROFILE\ATLAS-IA\dados_ibama_notif\notificacoes.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$todos = $dados.notificacoes
Write-Host ("notificacoes a carregar: " + $todos.Count)

$lote = 300
$total = 0
for ($i = 0; $i -lt $todos.Count; $i += $lote) {
  $fim = [Math]::Min($i + $lote - 1, $todos.Count - 1)
  $corpo = @{ notificacoes = $todos[$i..$fim] } | ConvertTo-Json -Depth 6 -Compress
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
Write-Host "Obs: o arquivo publico repete um numero de notificacao (3U75N76D)," -ForegroundColor DarkGray
Write-Host "por isso o total na base fica um abaixo do numero de linhas enviadas." -ForegroundColor DarkGray
