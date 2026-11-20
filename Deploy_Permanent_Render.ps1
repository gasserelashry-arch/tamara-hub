# Deploys Tamara Hub to Render with a permanent URL (PC can be off).
# Prerequisites: render login (done), GitHub auth via: gh auth login
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$gh = "$env:TEMP\gh-cli\bin\gh.exe"
if (-not (Test-Path $gh)) { $gh = 'gh' }

Write-Host 'Checking GitHub auth...' -ForegroundColor Yellow
& $gh auth status
if ($LASTEXITCODE -ne 0) {
  Write-Host 'Not logged into GitHub. Starting browser login...' -ForegroundColor Yellow
  & $gh auth login --hostname github.com --git-protocol https --web
}

$adminPass = $env:ADMIN_PASS
if (-not $adminPass -and (Test-Path '.\admin_pass.txt')) {
  $adminPass = (Get-Content '.\admin_pass.txt' -Raw).Trim()
}
if (-not $adminPass) { throw 'Missing ADMIN_PASS / admin_pass.txt' }

python .\_restore_and_prep_deploy.py

# Commit deployable files (secrets stay gitignored)
git add index.html PUBLIC_LINK.txt render.yaml Dockerfile requirements.txt tamara_hub_server.py Restart_Public_Link.bat Restart_Public_Link.ps1 Deploy_Permanent_Render.ps1 .gitignore README.md README_Hosting_Guide.txt official_issue_types.json build_issue_types.py 2>$null
git status --porcelain
git commit -m "Prepare permanent cloud deploy with latest macros and workflows" 2>$null

$user = (& $gh api user --jq .login)
$repoName = 'tamara-hub'
$full = "$user/$repoName"
$exists = $true
try { & $gh repo view $full 2>$null | Out-Null } catch { $exists = $false }
if (-not $exists -or $LASTEXITCODE -ne 0) {
  Write-Host "Creating private GitHub repo $full ..." -ForegroundColor Yellow
  & $gh repo create $repoName --private --source=. --remote=origin --push
} else {
  if (-not (git remote get-url origin 2>$null)) {
    git remote add origin "https://github.com/$full.git"
  }
  git push -u origin main
}

$repoUrl = "https://github.com/$full"
Write-Host "Deploying to Render from $repoUrl ..." -ForegroundColor Yellow
render workspace set tea-dbvcvas9v7es739cipb0 | Out-Null

# Create free web service
$out = render services create `
  --name tamara-hub `
  --type web_service `
  --repo $repoUrl `
  --branch main `
  --runtime python `
  --build-command 'pip install -r requirements.txt' `
  --start-command 'python tamara_hub_server.py' `
  --plan free `
  --health-check-path /api/health `
  --env-var "ADMIN_PASS=$adminPass" `
  --env-var 'PYTHON_VERSION=3.12.0' `
  --confirm `
  --output json

$out | Set-Content -Path '.\render_service_create.json' -Encoding UTF8
Write-Host $out

# Try extract URL
try {
  $j = $out | ConvertFrom-Json
  $url = $j.serviceUrl
  if (-not $url) { $url = $j.service.serviceDetails.url }
  if (-not $url -and $j.dashboardUrl) { $url = $j.dashboardUrl }
  if ($url) {
    @"
PERMANENT AGENT LINK (cloud — PC can be off)
============================================

$url

Hosted on Render free tier.
Note: free services may sleep after ~15 min idle; first open can take 30-60s to wake.
The URL itself never expires.

Admin password: see admin_pass.txt (do not share with agents).
"@ | Set-Content PUBLIC_LINK.txt -Encoding UTF8
    Write-Host "PERMANENT URL: $url" -ForegroundColor Green
  }
} catch {
  Write-Host 'Created service — open Render dashboard for the .onrender.com URL' -ForegroundColor Yellow
}
