param(
  [string]$Version = (Get-Date -Format "yyyyMMdd-HHmmss"),
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$repoRootPath = $repoRoot.Path

function Assert-Inside {
  param([string]$Path, [string]$Root)
  $resolved = [System.IO.Path]::GetFullPath($Path)
  $resolvedRoot = [System.IO.Path]::GetFullPath($Root)
  if (-not $resolved.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to operate outside workspace: $resolved"
  }
  return $resolved
}

function Remove-Inside {
  param([string]$Path, [string]$Root)
  if (Test-Path -LiteralPath $Path) {
    $resolved = Assert-Inside -Path $Path -Root $Root
    Remove-Item -LiteralPath $resolved -Recurse -Force
  }
}

$venvDir = Join-Path $scriptDir ".venv-build"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
  python -m venv $venvDir
}

if (-not $SkipInstall) {
  & $pythonExe -m pip install -U pip
  & $pythonExe -m pip install -r (Join-Path $scriptDir "requirements-release.txt")
}

$distDir = Join-Path $scriptDir "dist"
$buildDir = Join-Path $scriptDir "build"
$specPath = Join-Path $scriptDir "DistilledTI-Senren-Companion.spec"
Remove-Inside -Path $distDir -Root $scriptDir
Remove-Inside -Path $buildDir -Root $scriptDir
if (Test-Path -LiteralPath $specPath) {
  Remove-Item -LiteralPath (Assert-Inside -Path $specPath -Root $scriptDir) -Force
}

Push-Location $scriptDir
try {
  & $pythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name "DistilledTI-Senren-Companion" `
    --distpath $distDir `
    --workpath $buildDir `
    --specpath $scriptDir `
    --hidden-import tkinter `
    --hidden-import PIL `
    --hidden-import PIL.ImageGrab `
    --hidden-import pytesseract `
    companion.py
} finally {
  Pop-Location
}

$exePath = Join-Path $distDir "DistilledTI-Senren-Companion.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
  throw "Build failed: $exePath not found"
}

$releaseDir = Join-Path $repoRootPath "dist\senren-local-companion-$Version"
$releaseZip = Join-Path $repoRootPath "dist\senren-local-companion-$Version-windows.zip"
Remove-Inside -Path $releaseDir -Root $repoRootPath
if (Test-Path -LiteralPath $releaseZip) {
  Remove-Item -LiteralPath (Assert-Inside -Path $releaseZip -Root $repoRootPath) -Force
}
New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null

Copy-Item -LiteralPath $exePath -Destination (Join-Path $releaseDir "DistilledTI-Senren-Companion.exe") -Force
Copy-Item -LiteralPath (Join-Path $scriptDir ".env.example") -Destination (Join-Path $releaseDir ".env.example") -Force
Copy-Item -LiteralPath (Join-Path $scriptDir "README.md") -Destination (Join-Path $releaseDir "README.md") -Force
Copy-Item -LiteralPath (Join-Path $scriptDir "DEPLOYMENT.md") -Destination (Join-Path $releaseDir "DEPLOYMENT.md") -Force

@"
@echo off
cd /d "%~dp0"
DistilledTI-Senren-Companion.exe
"@ | Set-Content -LiteralPath (Join-Path $releaseDir "run.bat") -Encoding ASCII

@"
# Distilled TI Senren Companion Release

1. Double-click `run.bat` or `DistilledTI-Senren-Companion.exe`.
2. Open `http://127.0.0.1:17877` if the browser does not open automatically.
3. Fill the DSTI site/API address, login by email code, select the local game directory, then start the server record.
4. Clipboard capture works out of the box. OCR requires local Tesseract and optional `.env` settings copied from `.env.example`.

The exe reads `.env` from this same folder if present. Do not put user account secrets into this release folder before redistribution.
"@ | Set-Content -LiteralPath (Join-Path $releaseDir "QUICKSTART.md") -Encoding UTF8

Compress-Archive -LiteralPath $releaseDir -DestinationPath $releaseZip -Force
if (Test-Path -LiteralPath $specPath) {
  Remove-Item -LiteralPath (Assert-Inside -Path $specPath -Root $scriptDir) -Force
}
$sizeMb = [math]::Round((Get-Item -LiteralPath $releaseZip).Length / 1MB, 2)
Write-Output "release_dir=$releaseDir"
Write-Output "release_zip=$releaseZip"
Write-Output "size_mb=$sizeMb"
