# Publish latest hub (embedded data) to the permanent free agent link (GitHub Pages).
# No payment. Laptop can be off after publish — agents keep the same URL.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$gh = "$env:TEMP\gh-cli\bin\gh.exe"
if (-not (Test-Path $gh)) { $gh = 'gh' }

Write-Host 'Publish checklist (recommended):' -ForegroundColor Cyan
Write-Host '  1) Sync_Atlas_Recommended.bat (Transfers + KB mismatch + opsHealth)' -ForegroundColor Cyan
Write-Host '  2) embed + push (this script)' -ForegroundColor Cyan
Write-Host '  3) Open Pages URL with ?cb=<commit> and confirm Transfers SLA loads' -ForegroundColor Cyan
Write-Host '  4) If agents see old content: Reload published hub (clear cache) or Ctrl+F5' -ForegroundColor Cyan
Write-Host ''

Write-Host 'Embedding latest hub_store into index.html...' -ForegroundColor Yellow
python .\_embed_store.py
if (Test-Path .\_patch_ops_ui.py) {
  Write-Host 'Refreshing ops UI / revision badge...' -ForegroundColor Yellow
  python .\_patch_ops_ui.py
}
Write-Host 'Hiding sheet/doc filenames from agent UI...' -ForegroundColor Yellow
python .\_scrub_filenames_from_ui.py
Write-Host 'Checking index.html JavaScript syntax (blocks frozen UI)...' -ForegroundColor Yellow
python .\_check_index_js.py
if ($LASTEXITCODE -ne 0) {
  Write-Host 'PUBLISH ABORTED — fix the JS syntax error first (tabs/clicks would not work).' -ForegroundColor Red
  exit 1
}
# Prefer a descriptive publish message with store revision when available
$hubRev = ''
try {
  $hubRev = (python -c "import json; print(json.load(open('hub_store.json',encoding='utf-8')).get('revision',''))").Trim()
} catch {}
$commitMsg = if ($hubRev) { "Publish agent hub snapshot (rev $hubRev)" } else { "Publish agent hub snapshot" }

# Ensure Pages site exists (free, no card)
try {
  & $gh api repos/gasserelashry-arch/tamara-hub/pages 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) {
    $body = '{"build_type":"legacy","source":{"branch":"main","path":"/"}}'
    $body | & $gh api repos/gasserelashry-arch/tamara-hub/pages -X POST --input - | Out-Null
  }
} catch {}

# Only publish hub files — ignore local helper scripts / reports (they are not the agent site).
git add -- index.html PUBLIC_LINK.txt Publish_For_Agents.ps1 Publish_For_Agents.bat assets/atlas-greek-option-b.jpg assets/atlas-greek-bg-plate.jpg assets/atlas-greek-option-light.jpg assets/greek-meander-light.svg assets/greek-meander-dark.svg assets/greek-meander-nav.svg assets/greek-meander-banner-gold.svg 2>$null

# One-off author for this commit only (does NOT change global git config).
$gitAuthorName = 'gasser.elashry'
$gitAuthorEmail = 'gasser.elashry@tamara.co'

# Staged changes only (ignore untracked _*.py / report JSON noise)
$staged = git diff --cached --name-only
if ($staged) {
  Write-Host 'Staged for publish:' -ForegroundColor Yellow
  $staged | ForEach-Object { Write-Host "  $_" }
  git -c user.name="$gitAuthorName" -c user.email="$gitAuthorEmail" commit -m "$commitMsg"
  if ($LASTEXITCODE -ne 0) {
    Write-Host 'Commit failed. Updates were NOT pushed.' -ForegroundColor Red
    exit 1
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
  } else {
    Write-Host 'PUBLISH OK — agent link updated.' -ForegroundColor Green
  }
} else {
  Write-Host 'ALREADY UP TO DATE — nothing new in index.html to publish (not a failure).' -ForegroundColor Green
  Write-Host 'Agent link already has the latest snapshot. Untracked helper files are ignored.' -ForegroundColor Yellow
}

Write-Host 'Confirm tips (local / origin / public):' -ForegroundColor Cyan
git log -1 --oneline
git log origin/main -1 --oneline 2>$null
git log public/main -1 --oneline 2>$null

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
