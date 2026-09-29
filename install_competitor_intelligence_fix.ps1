$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backendTarget = Join-Path $root "backend\services\competitor_service.py"
$frontendTarget = Join-Path $root "frontend\src\components\Competitors.tsx"
$backendPatch = Join-Path $root "competitor_service.py"
$frontendPatch = Join-Path $root "Competitors.tsx"

if (-not (Test-Path -LiteralPath $backendTarget)) {
    throw "backend\services\competitor_service.py not found: $backendTarget"
}
if (-not (Test-Path -LiteralPath $frontendTarget)) {
    throw "frontend\src\components\Competitors.tsx not found: $frontendTarget"
}
if (-not (Test-Path -LiteralPath $backendPatch)) {
    throw "Patch file not found: $backendPatch"
}
if (-not (Test-Path -LiteralPath $frontendPatch)) {
    throw "Patch file not found: $frontendPatch"
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $root (".competitor-fix-backup\" + $timestamp)
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

Copy-Item -LiteralPath $backendTarget -Destination (Join-Path $backupDir "competitor_service.py")
Copy-Item -LiteralPath $frontendTarget -Destination (Join-Path $backupDir "Competitors.tsx")

Copy-Item -LiteralPath $backendPatch -Destination $backendTarget -Force
Copy-Item -LiteralPath $frontendPatch -Destination $frontendTarget -Force

$python = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "python" }

& $python -m py_compile $backendTarget
if ($LASTEXITCODE -ne 0) {
    Copy-Item -LiteralPath (Join-Path $backupDir "competitor_service.py") -Destination $backendTarget -Force
    Copy-Item -LiteralPath (Join-Path $backupDir "Competitors.tsx") -Destination $frontendTarget -Force
    throw "Python compile failed. Original files were restored from $backupDir"
}

Write-Host ""
Write-Host "Competitor Intelligence fix installed successfully." -ForegroundColor Green
Write-Host "Changed only:" -ForegroundColor Cyan
Write-Host "  backend\services\competitor_service.py"
Write-Host "  frontend\src\components\Competitors.tsx"
Write-Host "Backup: $backupDir" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Next: restart FastAPI, rebuild/restart the frontend, then run a NEW competitor analysis with both domains filled in." -ForegroundColor Yellow
