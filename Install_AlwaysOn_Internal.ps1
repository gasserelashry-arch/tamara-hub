# Installs Tamara Hub auto-start on this Tamara PC (no external cloud).
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Starter = Join-Path $Root 'Start_Tamara_Hub_Silent.bat'
$TaskName = 'TamaraHubAlwaysOn'

if (-not (Test-Path (Join-Path $Root 'admin_pass.txt'))) {
  throw 'admin_pass.txt missing — create it first.'
}

$bat = @"
@echo off
cd /d "$Root"
if not defined ADMIN_PASS (
  if exist "admin_pass.txt" set /p ADMIN_PASS=<admin_pass.txt
)
set PORT=8080
where python >nul 2>&1 && start "Tamara Hub" /MIN python tamara_hub_server.py && exit /b
where py >nul 2>&1 && start "Tamara Hub" /MIN py -3 tamara_hub_server.py && exit /b
"@
Set-Content -Path $Starter -Value $bat -Encoding ASCII

# Firewall (best-effort; may need admin)
try {
  netsh advfirewall firewall show rule name="Tamara Hub 8080" | Out-Null
  if ($LASTEXITCODE -ne 0) {
    netsh advfirewall firewall add rule name="Tamara Hub 8080" dir=in action=allow protocol=TCP localport=8080 profile=any | Out-Null
  }
} catch {}

$autoMethod = 'none'
# Prefer scheduled task; fall back to Startup folder (no admin)
try {
  $action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c `"$Starter`"" -WorkingDirectory $Root
  $trigger = New-ScheduledTaskTrigger -AtLogOn
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
  $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
  $autoMethod = "Scheduled Task: $TaskName"
} catch {
  $startup = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
  $cmdPath = Join-Path $startup 'TamaraHubAlwaysOn.cmd'
  Set-Content -Path $cmdPath -Value "@echo off`r`ncall `"$Starter`"" -Encoding ASCII
  $autoMethod = "Startup folder: $cmdPath"
}

# Ensure server is up now
try {
  Invoke-WebRequest -Uri 'http://127.0.0.1:8080/api/version' -UseBasicParsing -TimeoutSec 2 | Out-Null
} catch {
  Start-Process -FilePath 'cmd.exe' -ArgumentList "/c `"$Starter`"" -WindowStyle Minimized
  Start-Sleep 3
}

$hostname = $env:COMPUTERNAME
$ips = @(Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
  Select-Object -ExpandProperty IPAddress -Unique)

$primary = "http://${hostname}:8080"
$lines = @(
  'PERMANENT TAMARA-INTERNAL AGENT LINK',
  '====================================',
  '',
  'No external cloud. Hub runs on Tamara network only.',
  'Agents must be on Tamara VPN or office LAN.',
  '',
  'SHARE THIS WITH AGENTS (primary):',
  "  $primary",
  '',
  'Backup IPs (if hostname does not resolve):'
)
foreach ($ip in $ips) { $lines += "  http://${ip}:8080" }
$lines += @(
  '',
  "Machine: $hostname",
  "Auto-start: $autoMethod",
  '',
  'RULES:',
  '1) This machine must stay ON and logged into Windows for the link to work.',
  '2) Laptop shut down = hub offline (required without external hosting).',
  '3) For 24/7 with your laptop closed: ask Tamara IT for an always-on internal',
  '   VM/server, copy this package there, run Install_AlwaysOn_Internal.bat,',
  '   then share http://<server-hostname>:8080 with agents.',
  '',
  'Update Hub: open the same link, unlock AI Update Agent, save — agents on',
  'this same internal URL get live updates automatically.',
  '',
  'Admin password: admin_pass.txt (never share with agents).'
)
$lines -join "`r`n" | Set-Content -Path (Join-Path $Root 'PUBLIC_LINK.txt') -Encoding UTF8

Write-Host ''
Write-Host 'Always-on INTERNAL hub ready.' -ForegroundColor Green
Write-Host "Agent permanent link: $primary" -ForegroundColor Cyan
foreach ($ip in $ips) { Write-Host "  backup: http://${ip}:8080" }
Write-Host "Auto-start via: $autoMethod"
Write-Host ''
