param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

if (-not (Test-Path -LiteralPath $backendDir)) {
    throw "Missing backend directory: $backendDir"
}

if (-not (Test-Path -LiteralPath $frontendDir)) {
    throw "Missing frontend directory: $frontendDir"
}

$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $backendPython)) {
    $backendPython = "python"
}

$publicBackendCommand = "`"$backendPython`" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
$adminBackendCommand = "`"$backendPython`" -m uvicorn app.admin_main:app --reload --host 127.0.0.1 --port 8001"
$frontendCommand = "npm run dev"

if ($DryRun) {
    Write-Host "Backend dir        : $backendDir"
    Write-Host "Frontend dir       : $frontendDir"
    Write-Host "Public backend cmd : $publicBackendCommand"
    Write-Host "Admin backend cmd  : $adminBackendCommand"
    Write-Host "Frontend cmd       : $frontendCommand"
    exit 0
}

Start-Process powershell.exe -WorkingDirectory $backendDir -ArgumentList @(
    "-NoExit",
    "-Command",
    $publicBackendCommand
)

Start-Sleep -Milliseconds 400

Start-Process powershell.exe -WorkingDirectory $backendDir -ArgumentList @(
    "-NoExit",
    "-Command",
    $adminBackendCommand
)

Start-Sleep -Milliseconds 400

Start-Process powershell.exe -WorkingDirectory $frontendDir -ArgumentList @(
    "-NoExit",
    "-Command",
    $frontendCommand
)

Write-Host "Started public backend, admin backend, and frontend."
Write-Host "Public API : http://127.0.0.1:8000/docs"
Write-Host "Admin API  : http://127.0.0.1:8001/docs"
Write-Host "Frontend   : http://127.0.0.1:3000"
