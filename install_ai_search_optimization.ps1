$ErrorActionPreference = 'Stop'

$Root = (Get-Location).Path
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$MainFile = Join-Path $Backend 'main.py'
$BackendSource = Join-Path $Root 'ai_search_optimization.py'
$FrontendSource = Join-Path $Root 'AISearch.tsx'
$BackendTarget = Join-Path $Backend 'ai_search_optimization.py'
$FrontendTarget = Join-Path $Frontend 'src\components\AISearch.tsx'

if (-not (Test-Path $MainFile)) { throw "backend\main.py was not found. Run this from the project root." }
if (-not (Test-Path $BackendSource)) { throw "ai_search_optimization.py was not found beside this script." }
if (-not (Test-Path $FrontendSource)) { throw "AISearch.tsx was not found beside this script." }
if (-not (Test-Path $Frontend)) { throw "frontend folder was not found." }

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$mainBackup = "$MainFile.ai-search-backup-$timestamp"
$componentBackup = "$FrontendTarget.ai-search-backup-$timestamp"

Copy-Item $MainFile $mainBackup -Force
if (Test-Path $FrontendTarget) { Copy-Item $FrontendTarget $componentBackup -Force }

Copy-Item $BackendSource $BackendTarget -Force
Copy-Item $FrontendSource $FrontendTarget -Force

$mainText = [System.IO.File]::ReadAllText($MainFile)

$importLine = 'from ai_search_optimization import router as ai_search_optimization_router'
if ($mainText -notmatch '(?m)^from ai_search_optimization import router as ai_search_optimization_router\s*$') {
    $anchor = 'from content_automation import router as content_automation_router'
    if ($mainText.Contains($anchor)) {
        $mainText = $mainText.Replace($anchor, $anchor + "`r`n" + $importLine)
    } else {
        throw 'Could not find the existing content_automation router import. Main.py was not modified.'
    }
}

$includeBlock = @'
app.include_router(
    ai_search_optimization_router,
    tags=["AI Search Optimization"],
)
'@
if ($mainText -notmatch 'app\.include_router\(\s*ai_search_optimization_router\b') {
    $anchorPattern = '(?ms)(app\.include_router\(\s*content_automation_router,\s*tags=\["Content Automation"\],\s*\)\s*)'
    if ([regex]::IsMatch($mainText, $anchorPattern)) {
        $mainText = [regex]::Replace($mainText, $anchorPattern, '$1' + "`r`n" + $includeBlock.Trim() + "`r`n", 1)
    } elseif ($mainText -match '(?ms)app\.include_router\(\s*rank_tracking_router,') {
        $mainText = [regex]::Replace($mainText, '(?ms)(app\.include_router\(\s*rank_tracking_router,)', $includeBlock.Trim() + "`r`n" + '$1', 1)
    } else {
        throw 'Could not find a safe router insertion point. Main.py was not modified.'
    }
}

[System.IO.File]::WriteAllText($MainFile, $mainText, (New-Object System.Text.UTF8Encoding($false)))

Push-Location $Backend
try {
    $python = Join-Path $Backend '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) { $python = 'python' }
    & $python -m py_compile '.\ai_search_optimization.py'
    if ($LASTEXITCODE -ne 0) { throw 'ai_search_optimization.py syntax validation failed.' }
    & $python -m py_compile '.\main.py'
    if ($LASTEXITCODE -ne 0) { throw 'main.py syntax validation failed.' }
} finally {
    Pop-Location
}

Push-Location $Frontend
try {
    if (Test-Path '.\package.json') {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend production build failed.' }
    }
} finally {
    Pop-Location
}

Write-Host ''
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host 'AI Search Optimization installed successfully.' -ForegroundColor Green
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host "Backend:  $BackendTarget" -ForegroundColor Green
Write-Host "Frontend: $FrontendTarget" -ForegroundColor Green
Write-Host "Main:     $MainFile" -ForegroundColor Green
Write-Host ''
Write-Host 'Backups:' -ForegroundColor Yellow
Write-Host "  $mainBackup"
if (Test-Path $componentBackup) { Write-Host "  $componentBackup" }
Write-Host ''
Write-Host 'Only the AI Search feature files and the main router registration were changed.' -ForegroundColor Green
Write-Host 'No database migration is required.' -ForegroundColor Green
Write-Host ''
Write-Host 'Git safety:' -ForegroundColor Cyan
Write-Host '  git diff --check'
Write-Host '  git status --short'
Write-Host '  git add backend/main.py backend/ai_search_optimization.py frontend/src/components/AISearch.tsx'
Write-Host '  git diff --cached --name-only'
Write-Host '  git diff --cached --check'
Write-Host '  git commit -m "Add AI Search content optimization workflow"'
Write-Host '  git push'
