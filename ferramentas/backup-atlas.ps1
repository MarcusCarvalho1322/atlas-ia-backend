# Copia de seguranca do ATLAS.
#
# Guarda o que NAO se regenera: os casos abertos com sua auditoria, o status
# comercial de cada auto (selecionado, contatado, descartado, cliente), as
# notas da equipe e o registro de acesso. A carteira, os termos, as
# notificacoes e a divida ativa NAO entram — sao recorte de arquivo publico e
# voltam com uma mineracao e tres cargas.
#
# O arquivo fica pequeno de proposito. Arquivo pequeno e arquivo que alguem
# efetivamente guarda.
#
# A senha e lida do .env e nunca aparece na tela.

$envp    = "$env:USERPROFILE\ATLAS-IA\frontend\.env"
$destino = "$env:USERPROFILE\ATLAS-IA\backups"
$token = ((Get-Content $envp | Where-Object { $_ -match "^VITE_ATLAS_API_TOKEN=" }) -replace "^VITE_ATLAS_API_TOKEN=", "").Trim()
$H = @{ Authorization = ("Bearer " + $token) }

New-Item -ItemType Directory -Force -Path $destino | Out-Null
$carimbo = Get-Date -Format "yyyy-MM-dd_HHmm"
$arquivo = Join-Path $destino "atlas-backup-$carimbo.json"

try {
  $r = Invoke-RestMethod -Uri "https://atlas-geo.onrender.com/api/backup" -Headers $H -TimeoutSec 300
} catch {
  Write-Host ("FALHOU: " + $_.Exception.Message) -ForegroundColor Red
  exit 1
}

$r | ConvertTo-Json -Depth 12 | Set-Content -Path $arquivo -Encoding UTF8
$kb = [Math]::Round((Get-Item $arquivo).Length / 1KB, 1)

Write-Host ""
Write-Host ("  backup gravado: " + $arquivo) -ForegroundColor Green
Write-Host ("  tamanho: " + $kb + " KB")
Write-Host ""
Write-Host "  guardado (nao se regenera):"
Write-Host ("     casos abertos .............. " + $r.insubstituivel.casos.Count)
Write-Host ("     trabalho comercial ......... " + $r.insubstituivel.trabalho_comercial.Count)
Write-Host ("     registros de acesso ........ " + $r.insubstituivel.acessos.Count)
Write-Host ""
Write-Host "  so a contagem (se regenera do arquivo publico):"
Write-Host ("     prospectos ................. " + $r.regeneravel_apenas_contagem.prospectos)
Write-Host ("     termos ..................... " + $r.regeneravel_apenas_contagem.termos)
Write-Host ("     notificacoes ............... " + $r.regeneravel_apenas_contagem.notificacoes)
Write-Host ("     divida ativa ............... " + $r.regeneravel_apenas_contagem.divida_ativa)

# Mantem os 30 mais recentes. Backup que enche o disco vira backup desligado.
$antigos = Get-ChildItem $destino -Filter "atlas-backup-*.json" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 30
if ($antigos) {
  $antigos | Remove-Item -Force
  Write-Host ""
  Write-Host ("  (removidos " + $antigos.Count + " backups antigos; os 30 mais recentes ficam)") -ForegroundColor DarkGray
}
Write-Host ""
