# Deploy Tamara Hub to Render (run after: render login)
# Usage: .\deploy-to-render.ps1 -RepoUrl https://github.com/YOU/tamara-hub

param(
  [Parameter(Mandatory = $true)]
  [string]$RepoUrl,
  [string]$ServiceName = "tamara-hub",
  [string]$AdminPass = $env:ADMIN_PASS
)

$ErrorActionPreference = "Stop"
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

if (-not $AdminPass) {
  if (Test-Path ".\admin_pass.txt") {
    $AdminPass = (Get-Content ".\admin_pass.txt" -Raw).Trim()
  }
}
if (-not $AdminPass) {
  throw "Set ADMIN_PASS env var or create admin_pass.txt first."
}

Write-Host "Creating Render web service '$ServiceName' from $RepoUrl ..."
render services create `
  --name $ServiceName `
  --type web_service `
  --repo $RepoUrl `
  --runtime python `
  --build-command "pip install -r requirements.txt" `
  --start-command "python tamara_hub_server.py" `
  --plan free `
  --env-var "ADMIN_PASS=$AdminPass" `
  --confirm `
  --output text

Write-Host ""
Write-Host "Done. Open the service URL from the Render dashboard / CLI output and share it once with agents."
