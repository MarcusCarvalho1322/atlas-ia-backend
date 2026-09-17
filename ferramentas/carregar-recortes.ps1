# Carrega no ATLAS as fontes 5 a 8, na ordem:
#
#   1. termos      - versao ampliada: agora tambem doacao e destruicao
#   2. julgamentos - situacao do debito do auto (quitado, em cobranca...)
#   3. uc          - autos cuja coordenada cai dentro de UC federal (ICMBio)
#   4. autorizacoes- Sinaflor: autorizacao de supressao de vegetacao por CNPJ
#
# Os arquivos de origem ficam em dados_ibama_termos\ e sao recortes ja
# filtrados pela carteira. A carga e idempotente: rodar duas vezes nao
# duplica nada. A senha e lida do .env e nunca aparece na tela.

$envp  = "$env:USERPROFILE\ATLAS-IA\frontend\.env"
$token = ((Get-Content $envp | Where-Object { $_ -match "^VITE_ATLAS_API_TOKEN=" }) -replace "^VITE_ATLAS_API_TOKEN=", "").Trim()
if (-not $token) { Write-Host "Nao achei a senha no .env." -ForegroundColor Red; exit 1 }
$H    = @{ Authorization = ("Bearer " + $token); "Content-Type" = "application/json" }
$base = "https://atlas-geo.onrender.com"
$dir  = "$env:USERPROFILE\ATLAS-IA\dados_ibama_termos"

function Enviar {
  param($Titulo, $Url, $Itens, $Campo, $Lote = 300)

  Write-Host ""
  Write-Host ("== " + $Titulo + " ==") -ForegroundColor Cyan
  Write-Host ("   linhas a enviar: " + $Itens.Count)
  $total = 0
  for ($i = 0; $i -lt $Itens.Count; $i += $Lote) {
    $fim   = [Math]::Min($i + $Lote - 1, $Itens.Count - 1)
    $corpo = @{ $Campo = $Itens[$i..$fim] } | ConvertTo-Json -Depth 6 -Compress
    try {
      $r = Invoke-RestMethod -Method Post -Uri $Url -Headers $H -Body ([Text.Encoding]::UTF8.GetBytes($corpo)) -TimeoutSec 300
      $total = $r.total_na_base
      Write-Host ("   lote " + [int]($i/$Lote + 1) + ": " + $r.linhas_recebidas + " linhas  |  total na base " + $total)
    } catch {
      Write-Host ("   FALHOU no lote " + [int]($i/$Lote + 1) + ": " + $_.Exception.Message) -ForegroundColor Red
      return $null
    }
  }
  Write-Host ("   OK. total na base: " + $total) -ForegroundColor Green
  return $total
}

$arquivos = @(
  @{ nome="termos";       arq="termos.json";       chave="termos";        url="$base/api/termos/carregar";              campo="termos" },
  @{ nome="julgamentos";  arq="julgamentos.json";  chave="julgamentos";   url="$base/api/recorte/julgamentos/carregar"; campo="linhas" },
  @{ nome="uc";           arq="uc.json";           chave="autos_em_uc";   url="$base/api/recorte/uc/carregar";          campo="linhas" },
  @{ nome="autorizacoes"; arq="sinaflor.json";     chave="autorizacoes";  url="$base/api/recorte/autorizacoes/carregar";campo="linhas" }
)

$falta = $arquivos | Where-Object { -not (Test-Path (Join-Path $dir $_.arq)) }
if ($falta) {
  Write-Host "Faltam arquivos em dados_ibama_termos:" -ForegroundColor Red
  $falta | ForEach-Object { Write-Host ("   " + $_.arq) }
  exit 1
}

$resumo = @{}
foreach ($f in $arquivos) {
  $d = Get-Content (Join-Path $dir $f.arq) -Raw -Encoding UTF8 | ConvertFrom-Json
  $resumo[$f.nome] = Enviar -Titulo $f.nome -Url $f.url -Itens $d.($f.chave) -Campo $f.campo
}

Write-Host ""
Write-Host "============================================================"
Write-Host "  RESUMO" -ForegroundColor Cyan
foreach ($f in $arquivos) {
  $v = $resumo[$f.nome]
  if ($null -eq $v) { Write-Host ("   " + $f.nome.PadRight(14) + "FALHOU") -ForegroundColor Red }
  else              { Write-Host ("   " + $f.nome.PadRight(14) + $v + " na base") }
}
Write-Host "============================================================"
Write-Host ""
Write-Host "Diferencas esperadas entre enviado e total na base:" -ForegroundColor DarkGray
Write-Host "  termos       -19  o arquivo publico repete o mesmo termo" -ForegroundColor DarkGray
Write-Host "  autorizacoes -41  linhas identicas do mesmo imovel colapsam" -ForegroundColor DarkGray
Write-Host "Nos dois casos nao ha perda: o que se repete e a mesma linha." -ForegroundColor DarkGray
