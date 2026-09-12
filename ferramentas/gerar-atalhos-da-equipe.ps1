# Gera um atalho de entrada para cada pessoa da equipe.
#
# Cada atalho abre o console JA AUTENTICADO, sem ninguem digitar ou colar nada.
# A senha viaja depois do "#" do endereco: essa parte NUNCA e enviada ao
# servidor (nao entra em log nem em Referer) e a propria pagina a apaga da
# barra de enderecos no instante seguinte.
#
# Fonte: a linha ATLAS_API_TOKENS do cofre - a mesma que esta no Render.
# Este script NAO mostra nenhuma senha na tela: informa so os nomes.

$cofre   = "$env:USERPROFILE\ATLAS-IA\docs\ACESSOS-EQUIPE.txt"
$destino = "$env:USERPROFILE\ATLAS-IA\atalhos-da-equipe"
$base    = "https://atlas-geo.onrender.com/console"

if (-not (Test-Path $cofre)) { Write-Host "Nao encontrei o cofre em $cofre" -ForegroundColor Red; exit }
New-Item -ItemType Directory -Force -Path $destino | Out-Null

# A linha dos acessos e a unica com varios pares nome:senha separados por virgula.
$linhaAcessos = Get-Content $cofre -Encoding UTF8 |
                Where-Object { $_ -match '^[A-Za-z][A-Za-z0-9_.-]*:[A-Za-z0-9_\-]{20,}(,|$)' } |
                Select-Object -First 1

if (-not $linhaAcessos) { Write-Host "Nao achei a linha de acessos no cofre." -ForegroundColor Red; exit }

$gerados = @()
foreach ($par in ($linhaAcessos -split ',')) {
    if ($par -match '^\s*([A-Za-z][A-Za-z0-9_.-]*)\s*:\s*([A-Za-z0-9_\-]{20,})\s*$') {
        $nome  = $Matches[1].Trim()
        $senha = $Matches[2].Trim()
        $arquivo = Join-Path $destino ("ATLAS - " + $nome + ".url")
        [System.IO.File]::WriteAllText(
            $arquivo,
            "[InternetShortcut]`r`nURL=$base#k=$senha`r`n",
            (New-Object System.Text.ASCIIEncoding))
        $gerados += $nome
    }
}

Write-Host ""
if ($gerados.Count -eq 0) {
    Write-Host "  Nenhum acesso reconhecido." -ForegroundColor Yellow
} else {
    Write-Host ("  " + $gerados.Count + " atalhos gerados em:") -ForegroundColor Green
    Write-Host "  $destino" -ForegroundColor Green
    Write-Host ""
    foreach ($n in $gerados) { Write-Host ("   ATLAS - " + $n + ".url") }
    Write-Host ""
    Write-Host "  Cada arquivo carrega a senha da pessoa. Mande APENAS o arquivo dela." -ForegroundColor DarkGray
}
Write-Host ""
