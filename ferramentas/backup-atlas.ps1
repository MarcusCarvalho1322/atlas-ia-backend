# Copia de seguranca do ATLAS.
#
# Guarda o que NAO se regenera: os casos abertos com sua auditoria, o status
# comercial de cada auto (selecionado, contatado, descartado, cliente), as
# notas da equipe e o registro de acesso. Os recortes de fonte publica —
# carteira, termos, notificacoes, divida ativa, julgamentos, autos em UC e
# autorizacoes — NAO entram: voltam com uma mineracao e as cargas de
# ferramentas\, e o arquivo guarda so a contagem de cada um, para conferir a
# restauracao.
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
# A lista NAO fica fixa aqui. Quando os recortes de 17/09 entraram, esta tela
# continuou mostrando quatro linhas por estar escrita a mao, e fonte que nao
# aparece na conferencia e fonte que ninguem percebe faltando. Agora a tela
# percorre o que o proprio backup declara: fonte nova aparece sozinha.
Write-Host "  so a contagem (se regenera do arquivo publico):"
$inv = $r.regeneravel_apenas_contagem
$inv.PSObject.Properties | ForEach-Object {
  $rotulo = ($_.Name -replace "_", " ")
  Write-Host ("     " + $rotulo.PadRight(26, ".") + " " + $_.Value)
}
$zeradas = @($inv.PSObject.Properties | Where-Object { [int]$_.Value -eq 0 })
if ($zeradas) {
  Write-Host ""
  Write-Host ("  ATENCAO: " + $zeradas.Count + " fonte(s) com zero registros: " +
              (($zeradas | ForEach-Object { $_.Name }) -join ", ")) -ForegroundColor Yellow
  Write-Host "  Zero aqui e carga que faltou, nao fonte que nao existe." -ForegroundColor Yellow
}

# Mantem os 30 mais recentes. Backup que enche o disco vira backup desligado.
$antigos = Get-ChildItem $destino -Filter "atlas-backup-*.json" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 30
if ($antigos) {
  $antigos | Remove-Item -Force
  Write-Host ""
  Write-Host ("  (removidos " + $antigos.Count + " backups antigos; os 30 mais recentes ficam)") -ForegroundColor DarkGray
}
Write-Host ""
