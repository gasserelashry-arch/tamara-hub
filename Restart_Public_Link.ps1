# Restarts Tamara Hub public Cloudflare quick tunnel and writes PUBLIC_LINK.txt
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$adminPassFile = Join-Path $Root 'admin_pass.txt'
if (-not $env:ADMIN_PASS -and (Test-Path $adminPassFile)) {
  $env:ADMIN_PASS = (Get-Content $adminPassFile -Raw).Trim()
}
if (-not $env:ADMIN_PASS) {
  Write-Host 'Missing ADMIN_PASS / admin_pass.txt' -ForegroundColor Red
  exit 1
}
$env:PORT = '8080'

function Test-Hub {
  try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/api/version' -UseBasicParsing -TimeoutSec 3
    return $r.StatusCode -eq 200
  } catch { return $false }
}

if (-not (Test-Hub)) {
  Write-Host 'Starting Tamara Hub server on :8080 ...' -ForegroundColor Yellow
  Start-Process -FilePath 'python' -ArgumentList 'tamara_hub_server.py' -WorkingDirectory $Root -WindowStyle Minimized
  for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Hub) { break }
  }
}
if (-not (Test-Hub)) {
  Write-Host 'Hub server failed to start on http://127.0.0.1:8080' -ForegroundColor Red
  exit 1
}
Write-Host 'Hub server OK on http://127.0.0.1:8080' -ForegroundColor Green

Get-Process -Name cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$cloudflared = $null
if (Get-Command cloudflared -ErrorAction SilentlyContinue) {
  $cloudflared = (Get-Command cloudflared).Source
} elseif (Test-Path "$env:TEMP\cloudflared.exe") {
  $cloudflared = "$env:TEMP\cloudflared.exe"
}
if (-not $cloudflared) {
  Write-Host 'cloudflared not found. Install Cloudflare tunnel CLI first.' -ForegroundColor Red
  exit 1
}

$log = Join-Path $env:TEMP 'tamara_hub_tunnel.log'
if (Test-Path $log) { Remove-Item $log -Force }
Write-Host 'Starting public Cloudflare tunnel...' -ForegroundColor Yellow
$proc = Start-Process -FilePath $cloudflared -ArgumentList @('tunnel','--url','http://127.0.0.1:8080') -RedirectStandardError $log -RedirectStandardOutput $log -PassThru -WindowStyle Minimized

$url = $null
for ($i = 0; $i -lt 45; $i++) {
  Start-Sleep -Seconds 1
  if (Test-Path $log) {
    $txt = Get-Content $log -Raw -ErrorAction SilentlyContinue
    if ($txt -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
      $url = $Matches[0]
      break
    }
  }
  if ($proc.HasExited) { break }
}

if (-not $url) {
  Write-Host 'Tunnel started but URL was not detected yet. Check the cloudflared window/log.' -ForegroundColor Red
  if (Test-Path $log) { Get-Content $log -Tail 30 }
  exit 1
}

$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'
@"
CURRENT PUBLIC LINK (agents can use this while your PC + tunnel are running)
=========================================================================

$url

Updated: $stamp
Verified after restart by Restart_Public_Link.ps1
Keep this PC awake and leave the tunnel running, or agents will see DNS/site errors.

Admin password: see admin_pass.txt (local only — never share with agents).

If the link dies again: run Restart_Public_Link.bat and share the NEW URL.
For a permanent never-changing URL, deploy to Render (README.md).
"@ | Set-Content -Path (Join-Path $Root 'PUBLIC_LINK.txt') -Encoding UTF8

Write-Host ''
Write-Host '========================================' -ForegroundColor Cyan
Write-Host " NEW AGENT LINK: $url" -ForegroundColor Green
Write-Host '========================================' -ForegroundColor Cyan
Write-Host 'Saved to PUBLIC_LINK.txt'
Write-Host 'Share this URL with agents (Ctrl+Click to open).'
Write-Host ''

try {
  $v = (Invoke-WebRequest -Uri "$url/api/version" -UseBasicParsing -TimeoutSec 30).Content
  Write-Host "Public /api/version => $v" -ForegroundColor Green
} catch {
  Write-Host "Tunnel URL created; public probe still warming up: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host 'Leave this window open. Press Ctrl+C only when you want to stop the public link.'
Wait-Process -Id $proc.Id
