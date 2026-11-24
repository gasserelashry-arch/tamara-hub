# Publish latest hub (embedded data) to the permanent free agent link (GitHub Pages).
# No payment. Laptop can be off after publish — agents keep the same URL.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$gh = "$env:TEMP\gh-cli\bin\gh.exe"
if (-not (Test-Path $gh)) { $gh = 'gh' }

Write-Host 'Embedding latest hub_store into index.html...' -ForegroundColor Yellow
python .\_embed_store.py

# Ensure Pages site exists (free, no card)
try {
  & $gh api repos/gasserelashry-arch/tamara-hub/pages 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) {
    $body = '{"build_type":"legacy","source":{"branch":"main","path":"/"}}'
    $body | & $gh api repos/gasserelashry-arch/tamara-hub/pages -X POST --input - | Out-Null
  }
} catch {}

git add index.html PUBLIC_LINK.txt Publish_For_Agents.ps1 Publish_For_Agents.bat 2>$null
git status --porcelain

# One-off author for this commit only (does NOT change global git config).
# Fixes: "Author identity unknown" when user.name / user.email are unset.
$gitAuthorName = 'gasser.elashry'
$gitAuthorEmail = 'gasser.elashry@tamara.co'
$status = git status --porcelain
if ($status) {
  git -c user.name="$gitAuthorName" -c user.email="$gitAuthorEmail" commit -m "Publish agent hub snapshot"
  if ($LASTEXITCODE -ne 0) {
    Write-Host 'Commit failed. Updates were NOT pushed.' -ForegroundColor Red
    exit 1
  }
} else {
  Write-Host 'No changes to commit (index already up to date).' -ForegroundColor Yellow
}

Write-Host 'Pushing to origin and public...' -ForegroundColor Yellow
git push origin main
if ($LASTEXITCODE -ne 0) {
  Write-Host 'Push to origin FAILED.' -ForegroundColor Red
  exit 1
}
git push public main
if ($LASTEXITCODE -ne 0) {
  Write-Host 'Push to public FAILED (Pages may be on origin only).' -ForegroundColor Yellow
}

Write-Host 'Push OK. Confirm remote tip matches local:' -ForegroundColor Green
git log -1 --oneline
git log origin/main -1 --oneline
git log public/main -1 --oneline

$url = 'https://gasserelashry-arch.github.io/tamara-hub/'
@"
PERMANENT AGENT LINK (FREE — no payment, laptop can be OFF)
===========================================================

$url

How it works:
- Agents always open the URL above (bookmark once).
- You edit on localhost (http://127.0.0.1:8080), then run Publish_For_Agents.bat
  to push updates to the permanent link.
- No Render, no tunnel, no card.

Note: First Pages enable can take 1-3 minutes. If 404, wait and refresh.
"@ | Set-Content PUBLIC_LINK.txt -Encoding UTF8

Write-Host ''
Write-Host "PERMANENT AGENT LINK: $url" -ForegroundColor Green
Write-Host 'Share that URL with agents. Your laptop can be closed after publish.'
Write-Host ''
