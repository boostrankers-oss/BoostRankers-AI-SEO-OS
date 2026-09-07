$ErrorActionPreference = 'Stop'

# ============================================================
# Boost Rankers - Keyword Conflicts SAFE FULL INSTALLER
# ============================================================
# Run this script from the project root:
# C:\Users\mdari\OneDrive\Desktop\BoostRankers-AI-SEO-OS
#
# This version preserves the original installer responsibilities,
# but uses the corrected 1,093-line backend feature file.
# It NEVER replaces App.tsx / Sidebar.tsx / main.py wholesale.
# ============================================================

$root = (Get-Location).Path
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$component = Join-Path $frontend 'src\components'

if (-not (Test-Path $backend)) { throw "backend folder not found: $backend" }
if (-not (Test-Path $frontend)) { throw "frontend folder not found: $frontend" }
if (-not (Test-Path $component)) { throw "frontend\src\components folder not found: $component" }

# ------------------------------------------------------------
# Source files
# ------------------------------------------------------------
# IMPORTANT: use the corrected backend, not the old 1,021-line copy.
$sourceBackend = Join-Path $root 'keyword_conflicts.fixed.py'
$sourceFrontend = Join-Path $root 'KeywordConflicts.tsx'

if (-not (Test-Path $sourceBackend)) {
    throw "Missing keyword_conflicts.fixed.py in project root."
}
if (-not (Test-Path $sourceFrontend)) {
    throw "Missing KeywordConflicts.tsx in project root."
}

# Safety check: corrected backend must contain the expanded implementation.
$backendLineCount = (Get-Content $sourceBackend).Count
if ($backendLineCount -lt 1050) {
    throw "Refusing to install: keyword_conflicts.fixed.py has only $backendLineCount lines. Expected the corrected expanded feature file (1,093 lines)."
}

$app = Join-Path $frontend 'src\App.tsx'
$sidebar = Join-Path $component 'Sidebar.tsx'
$backendMain = Join-Path $backend 'main.py'

foreach ($required in @($app, $sidebar, $backendMain)) {
    if (-not (Test-Path $required)) {
        throw "Required project file not found: $required"
    }
}

# ------------------------------------------------------------
# Backup everything this installer may edit
# ------------------------------------------------------------
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

$appBackup = "$app.keyword-conflicts-$stamp.bak"
$sidebarBackup = "$sidebar.keyword-conflicts-$stamp.bak"
$mainBackup = "$backendMain.keyword-conflicts-$stamp.bak"
$backendBackup = (Join-Path $backend "keyword_conflicts.py.keyword-conflicts-$stamp.bak")

Copy-Item $app $appBackup -Force
Copy-Item $sidebar $sidebarBackup -Force
Copy-Item $backendMain $mainBackup -Force

if (Test-Path (Join-Path $backend 'keyword_conflicts.py')) {
    Copy-Item (Join-Path $backend 'keyword_conflicts.py') $backendBackup -Force
}

# ------------------------------------------------------------
# Install feature files
# ------------------------------------------------------------
Copy-Item $sourceBackend (Join-Path $backend 'keyword_conflicts.py') -Force
Copy-Item $sourceFrontend (Join-Path $component 'KeywordConflicts.tsx') -Force

# ------------------------------------------------------------
# App.tsx - add only missing Keyword Conflicts pieces
# ------------------------------------------------------------
$appText = Get-Content $app -Raw

if ($appText -notmatch 'KeywordConflicts') {
    $appText = $appText -replace '(import \{ RankTracker \} from [^;]+;)', '$1`r`nimport { KeywordConflicts } from "@/components/KeywordConflicts";'
}

if ($appText -notmatch '"keywordconflicts"') {
    $appText = $appText -replace '(\| "ranktracker"\s*)', '$1  | "keywordconflicts"`r`n'
}

if ($appText -notmatch 'case "keywordconflicts"') {
    $appText = $appText -replace '(case "ranktracker":\s*return <RankTracker />;)', '$1`r`n      case "keywordconflicts": return <KeywordConflicts />;'
}

Set-Content $app -Value $appText -Encoding UTF8

# ------------------------------------------------------------
# Sidebar.tsx - add only missing Keyword Conflicts pieces
# ------------------------------------------------------------
$sidebarText = Get-Content $sidebar -Raw

if ($sidebarText -notmatch 'ShieldAlert') {
    $sidebarText = $sidebarText -replace '(Sun,\s*)', '$1  ShieldAlert,`r`n'
}

if ($sidebarText -notmatch 'id: "keywordconflicts"') {
    $sidebarText = $sidebarText -replace '(\{ id: "clusters", label: "Keyword Clusters", icon: Network \},)', '$1`r`n    { id: "keywordconflicts", label: "Keyword Conflicts", icon: ShieldAlert },'
}

Set-Content $sidebar -Value $sidebarText -Encoding UTF8

# ------------------------------------------------------------
# main.py - add only missing router import/registration
# ------------------------------------------------------------
$mainText = Get-Content $backendMain -Raw

if ($mainText -notmatch 'from keyword_conflicts import router as keyword_conflicts_router') {
    $mainText = $mainText -replace '(from routers\.google_integration import router as google_integration)', '$1`r`nfrom keyword_conflicts import router as keyword_conflicts_router'
}

if ($mainText -notmatch 'keyword_conflicts_router') {
    throw 'Could not add Keyword Conflicts router import to main.py.'
}

if ($mainText -notmatch 'app\.include_router\(\s*keyword_conflicts_router') {
    $insert = @'

app.include_router(
    keyword_conflicts_router,
    tags=["Keyword Conflicts"],
)
'@

    if ($mainText -match '# ============================================================\r?\n# Health Check') {
        $mainText = [regex]::Replace(
            $mainText,
            '(# ============================================================\r?\n# Health Check)',
            ($insert + "`r`n" + '$1'),
            1
        )
    } else {
        $mainText += $insert
    }
}

Set-Content $backendMain -Value $mainText -Encoding UTF8

# ------------------------------------------------------------
# Validate the installed backend
# ------------------------------------------------------------
Push-Location $backend
try {
    python -m py_compile ".\keyword_conflicts.py"
    if ($LASTEXITCODE -ne 0) {
        throw "keyword_conflicts.py syntax validation failed."
    }

    python -m py_compile ".\main.py"
    if ($LASTEXITCODE -ne 0) {
        throw "main.py syntax validation failed."
    }
}
finally {
    Pop-Location
}

Write-Host ''
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host 'Keyword Conflicts feature installed successfully.' -ForegroundColor Green
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host "Corrected backend lines installed: $backendLineCount" -ForegroundColor Green
Write-Host ''
Write-Host 'Backups:' -ForegroundColor Yellow
Write-Host "  App.tsx      -> $appBackup"
Write-Host "  Sidebar.tsx  -> $sidebarBackup"
Write-Host "  main.py      -> $mainBackup"
if (Test-Path $backendBackup) {
    Write-Host "  keyword_conflicts.py -> $backendBackup"
}
Write-Host ''
Write-Host 'No existing feature files were replaced wholesale.' -ForegroundColor Green
Write-Host 'Restart Uvicorn and run a NEW Keyword Conflict scan.' -ForegroundColor Cyan
