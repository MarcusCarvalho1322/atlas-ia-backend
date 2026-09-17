# Agenda o backup do ATLAS para rodar sozinho, todo dia as 19h.
#
# Backup que depende de alguem lembrar nao e backup. Este registra uma tarefa
# no Agendador de Tarefas do Windows, que roda mesmo com o navegador fechado,
# e que dispara assim que a maquina liga se a hora ja tiver passado.
#
# Rode uma vez. Para conferir depois:  Get-ScheduledTask -TaskName "ATLAS backup"
# Para remover:  Unregister-ScheduledTask -TaskName "ATLAS backup" -Confirm:$false

$script = "$env:USERPROFILE\ATLAS-IA\ferramentas\backup-atlas.ps1"
if (-not (Test-Path $script)) {
  Write-Host "Nao encontrei $script" -ForegroundColor Red
  exit 1
}

$acao    = New-ScheduledTaskAction -Execute "powershell.exe" `
             -Argument ("-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`"")
$gatilho = New-ScheduledTaskTrigger -Daily -At 19:00
$config  = New-ScheduledTaskSettingsSet -StartWhenAvailable `
             -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
             -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

Register-ScheduledTask -TaskName "ATLAS backup" -Action $acao -Trigger $gatilho `
  -Settings $config -Description "Copia de seguranca diaria do ATLAS." -Force | Out-Null

Write-Host ""
Write-Host "  tarefa 'ATLAS backup' agendada para todo dia as 19h." -ForegroundColor Green
Write-Host "  se a maquina estiver desligada no horario, ela roda assim que ligar."
Write-Host ""
