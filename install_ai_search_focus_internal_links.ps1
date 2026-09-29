param(
    [string]$ProjectRoot = ''
)

$ErrorActionPreference = 'Stop'

if (-not $ProjectRoot) {
    try { $ProjectRoot = (& git rev-parse --show-toplevel 2>$null).Trim() } catch { $ProjectRoot = '' }
}
if (-not $ProjectRoot) { $ProjectRoot = (Get-Location).Path }
$ProjectRoot = (Resolve-Path $ProjectRoot).Path

$BackendTarget = Join-Path $ProjectRoot 'backend\ai_search_optimization.py'
$FrontendTarget = Join-Path $ProjectRoot 'frontend\src\components\AISearch.tsx'
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendSource = Join-Path $SourceDir 'ai_search_optimization.py'
$FrontendSource = Join-Path $SourceDir 'AISearch.tsx'

if (-not (Test-Path $BackendTarget)) { throw "Backend target not found: $BackendTarget" }
if (-not (Test-Path $FrontendTarget)) { throw "Frontend target not found: $FrontendTarget" }
if (-not (Test-Path $BackendSource)) { throw "Missing source file beside installer: $BackendSource" }
if (-not (Test-Path $FrontendSource)) { throw "Missing source file beside installer: $FrontendSource" }

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Copy-Item $BackendTarget "$BackendTarget.ai-search-focus-backup-$stamp" -Force
Copy-Item $FrontendTarget "$FrontendTarget.ai-search-focus-backup-$stamp" -Force
Copy-Item $BackendSource $BackendTarget -Force
Copy-Item $FrontendSource $FrontendTarget -Force

Push-Location (Join-Path $ProjectRoot 'backend')
try {
    if (Test-Path '.venv\Scripts\python.exe') {
        .\.venv\Scripts\python.exe -m py_compile .\ai_search_optimization.py
    } else {
        python -m py_compile .\ai_search_optimization.py
    }
    if ($LASTEXITCODE -ne 0) { throw 'Backend syntax validation failed.' }
}
finally { Pop-Location }

Push-Location $ProjectRoot
try {
    if (Test-Path 'frontend\package.json') {
        npm --prefix .\frontend run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend production build failed.' }
    }
}
finally { Pop-Location }

Write-Host ''
Write-Host 'AI Search enhancement installed successfully.' -ForegroundColor Green
Write-Host 'Automatic unused focus keyword + high-engagement title + verified WordPress internal linking are enabled.'
Write-Host 'Only these source files were changed:'
Write-Host '  backend\ai_search_optimization.py'
Write-Host '  frontend\src\components\AISearch.tsx'
Write-Host ''
Write-Host 'Review git diff, then stage ONLY those two files.' -ForegroundColor Yellow
