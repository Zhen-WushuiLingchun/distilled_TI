param(
  [int]$Port = 3101,
  [switch]$Install,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$nextchatDir = Join-Path $scriptDir "nextchat"
$envFile = Join-Path $nextchatDir ".env.local"
$templateFile = Join-Path $nextchatDir ".env.template"

if (-not (Test-Path -LiteralPath $nextchatDir)) {
  throw "NextChat demo directory not found: $nextchatDir"
}

if (-not (Test-Path -LiteralPath $envFile)) {
  if (Test-Path -LiteralPath $templateFile) {
    Copy-Item -LiteralPath $templateFile -Destination $envFile
    Write-Host "Created $envFile from .env.template. Fill model/backend keys before production use."
  } else {
    Write-Warning ".env.local is missing and no .env.template was found."
  }
}

Write-Host "Backend expected at DISTILLED_TI_API_BASE, default http://127.0.0.1:8000"
Write-Host "Admin dashboard: http://127.0.0.1:$Port/support-admin"

if ($DryRun) {
  Write-Host "Dry run complete. No server started."
  exit 0
}

Push-Location $nextchatDir
try {
  if ($Install -or -not (Test-Path -LiteralPath (Join-Path $nextchatDir "node_modules"))) {
    npm install --ignore-scripts --legacy-peer-deps --package-lock=false
  }
  $env:PORT = "$Port"
  npm run dev
} finally {
  Pop-Location
}
