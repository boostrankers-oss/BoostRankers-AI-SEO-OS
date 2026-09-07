$ErrorActionPreference = "Stop"

$RepoRoot = (Get-Location).Path
$BackendTarget = Join-Path $RepoRoot "backend\keyword_conflicts.py"
$FrontendTarget = Join-Path $RepoRoot "frontend\src\components\KeywordConflicts.tsx"
$BackendSource = Join-Path $PSScriptRoot "keyword_conflicts.fixed2.py"
$FrontendSource = Join-Path $PSScriptRoot "KeywordConflicts.tsx"

if (-not (Test-Path $BackendTarget)) { throw "Missing $BackendTarget. Run this script from the repository root." }
if (-not (Test-Path $FrontendTarget)) { throw "Missing $FrontendTarget. Run this script from the repository root." }
if (-not (Test-Path $BackendSource)) { throw "Missing patch file: $BackendSource" }
if (-not (Test-Path $FrontendSource)) { throw "Missing patch file: $FrontendSource" }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackendBackup = "$BackendTarget.bak-$stamp"
$FrontendBackup = "$FrontendTarget.bak-$stamp"

Write-Host "Backing up current Keyword Conflicts files..." -ForegroundColor Cyan
Copy-Item $BackendTarget $BackendBackup -Force
Copy-Item $FrontendTarget $FrontendBackup -Force

try {
    Write-Host "Installing isolated Keyword Conflicts backend fix..." -ForegroundColor Cyan
    Copy-Item $BackendSource $BackendTarget -Force

    Write-Host "Installing isolated Keyword Conflicts frontend fix..." -ForegroundColor Cyan
    Copy-Item $FrontendSource $FrontendTarget -Force

    Write-Host "Checking Python syntax..." -ForegroundColor Cyan
    Push-Location (Join-Path $RepoRoot "backend")
    python -m py_compile .\keyword_conflicts.py
    Pop-Location

    Write-Host "Building frontend..." -ForegroundColor Cyan
    Push-Location (Join-Path $RepoRoot "frontend")
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    Pop-Location

    Write-Host "`nKeyword Conflicts fix installed successfully." -ForegroundColor Green
    Write-Host "Only these files were changed:" -ForegroundColor Green
    Write-Host "  backend\keyword_conflicts.py"
    Write-Host "  frontend\src\components\KeywordConflicts.tsx"
    Write-Host "Backups:" -ForegroundColor DarkGray
    Write-Host "  $BackendBackup" -ForegroundColor DarkGray
    Write-Host "  $FrontendBackup" -ForegroundColor DarkGray
}
catch {
    Pop-Location -ErrorAction SilentlyContinue
    Write-Host "`nInstall/build failed. Restoring the original two files..." -ForegroundColor Yellow
    Copy-Item $BackendBackup $BackendTarget -Force
    Copy-Item $FrontendBackup $FrontendTarget -Force
    throw
}
