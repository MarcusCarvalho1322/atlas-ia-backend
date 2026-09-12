$envp = "$env:USERPROFILE\ATLAS-IA\frontend\.env"
Write-Host ""
if (-not (Test-Path $envp)) {
    Write-Host "  Nao encontrei o arquivo .env em:" -ForegroundColor Red
    Write-Host "  $envp" -ForegroundColor Red
} else {
    $linha = Get-Content $envp | Where-Object { $_ -match "^VITE_ATLAS_API_TOKEN=" }
    $token = $linha -replace "^VITE_ATLAS_API_TOKEN=", ""
    if ([string]::IsNullOrWhiteSpace($token)) {
        Write-Host "  A senha esta vazia no arquivo .env" -ForegroundColor Red
    } else {
        Set-Clipboard -Value $token
        Write-Host "  Senha de acesso copiada." -ForegroundColor Green
        Write-Host "  Cole no console com Ctrl+V." -ForegroundColor Green
        Write-Host ""
        Write-Host "  (a senha fica na area de transferencia ate voce copiar outra coisa)" -ForegroundColor DarkGray
    }
}
Write-Host ""
Start-Sleep -Seconds 5