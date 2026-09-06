$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = 'C:\Users\mdari\OneDrive\Desktop\BoostRankers-AI-SEO-OS'

if (-not (Test-Path -LiteralPath $project)) {
    throw "Project path not found: $project"
}

$frontend = Join-Path $project 'frontend\src'
$backend = Join-Path $project 'backend'
$nl = [Environment]::NewLine

function Backup-Once([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return }
    $backup = "$path.rank-tracker.bak"
    if (-not (Test-Path -LiteralPath $backup)) {
        Copy-Item -LiteralPath $path -Destination $backup -Force
        Write-Host "Backup: $backup"
    }
}

# 1) Add the new backend module. Existing backend modules are untouched.
Copy-Item -LiteralPath (Join-Path $root 'backend\rank_tracking.py') -Destination (Join-Path $backend 'rank_tracking.py') -Force

# 2) Register the new router in backend/main.py with a minimal, idempotent patch.
$main = Join-Path $backend 'main.py'
if (-not (Test-Path -LiteralPath $main)) { throw "backend/main.py not found" }
Backup-Once $main
$mainText = Get-Content -LiteralPath $main -Raw

if ($mainText -notmatch '(?m)^from rank_tracking import router as rank_tracking_router\s*$') {
    $googleImportPattern = '(?m)^(from routers\.google_integration import router as google_integration\s*)$'
    if ([regex]::IsMatch($mainText, $googleImportPattern)) {
        $mainText = [regex]::Replace($mainText, $googleImportPattern, '$1' + $nl + 'from rank_tracking import router as rank_tracking_router', 1)
    } else {
        $mainText = "from rank_tracking import router as rank_tracking_router$nl$mainText"
    }
}

if ($mainText -notmatch 'app\.include_router\(rank_tracking_router\)') {
    $healthPattern = '(?m)^@app\.get\("/api/health"\)'
    if ([regex]::IsMatch($mainText, $healthPattern)) {
        $mainText = [regex]::Replace($mainText, $healthPattern, "app.include_router(rank_tracking_router)$nl$nl`$0", 1)
    } else {
        $mainText = $mainText.TrimEnd() + $nl + $nl + 'app.include_router(rank_tracking_router)' + $nl
    }
}
Set-Content -LiteralPath $main -Value $mainText -Encoding UTF8

# 3) Add Rank Tracker to App.tsx without rewriting existing views.
$app = Join-Path $frontend 'App.tsx'
if (-not (Test-Path -LiteralPath $app)) { throw "frontend/src/App.tsx not found" }
Backup-Once $app
$appText = Get-Content -LiteralPath $app -Raw

if ($appText -notmatch 'components/RankTracker') {
    $backlinksImport = 'import { Backlinks } from "@/components/Backlinks";'
    if ($appText.Contains($backlinksImport)) {
        $appText = $appText.Replace($backlinksImport, $backlinksImport + $nl + 'import { RankTracker } from "@/components/RankTracker";')
    } else {
        throw 'App.tsx import marker for Backlinks not found. No App.tsx change was made.'
    }
}

if ($appText -notmatch '"ranktracker"') {
    $appText = [regex]::Replace($appText, '(?m)^(\s*\|\s*"backlinks"\s*)$', '$1' + $nl + '  | "ranktracker"', 1)
    if ($appText -notmatch '"ranktracker"') {
        throw 'App.tsx ViewKey marker for backlinks not found. No ViewKey change was made.'
    }
}

if ($appText -notmatch 'view === "ranktracker"') {
    $viewMarker = '{view === "backlinks" && <Backlinks />}'
    if ($appText.Contains($viewMarker)) {
        $appText = $appText.Replace($viewMarker, $viewMarker + $nl + '          {view === "ranktracker" && <RankTracker />}')
    } else {
        throw 'App.tsx render marker for Backlinks not found. No Rank Tracker render was added.'
    }
}
Set-Content -LiteralPath $app -Value $appText -Encoding UTF8

# 4) Add Rank Tracker to Sidebar.tsx only if the existing Backlinks marker exists.
$sidebar = Join-Path $frontend 'components\Sidebar.tsx'
if (Test-Path -LiteralPath $sidebar) {
    Backup-Once $sidebar
    $sidebarText = Get-Content -LiteralPath $sidebar -Raw
    if ($sidebarText -notmatch 'id: "ranktracker"') {
        $needle = '{ id: "backlinks", label: "Backlinks", icon: Link2 },'
        if (-not $sidebarText.Contains($needle)) {
            throw 'Sidebar navigation marker not found. No Sidebar changes were made.'
        }
        $replacement = $needle + $nl + '    { id: "ranktracker", label: "Rank Tracker", icon: Link2 },'
        $sidebarText = $sidebarText.Replace($needle, $replacement)
        Set-Content -LiteralPath $sidebar -Value $sidebarText -Encoding UTF8
    }
}

# 5) Add Rank Tracker to CommandPalette.tsx if its existing Backlinks item is present.
$palette = Join-Path $frontend 'components\CommandPalette.tsx'
if (Test-Path -LiteralPath $palette) {
    Backup-Once $palette
    $paletteText = Get-Content -LiteralPath $palette -Raw
    if ($paletteText -notmatch 'id: "ranktracker"') {
        $needle = '{ id: "backlinks", label: "Backlink Intelligence", icon: Link2 },'
        if ($paletteText.Contains($needle)) {
            $replacement = $needle + $nl + '    { id: "ranktracker", label: "Rank Tracker", icon: Link2 },'
            $paletteText = $paletteText.Replace($needle, $replacement)
            Set-Content -LiteralPath $palette -Value $paletteText -Encoding UTF8
        }
    }
}

Write-Host ''
Write-Host 'Rank Tracker installation patch completed successfully.' -ForegroundColor Green
Write-Host 'Existing modified files were backed up with .rank-tracker.bak.'
Write-Host 'New file: backend/rank_tracking.py'
Write-Host 'New file: frontend/src/components/RankTracker.tsx'
Write-Host ''
Write-Host 'Next verification:'
Write-Host '  cd backend'
Write-Host '  python -m py_compile rank_tracking.py'
Write-Host '  cd ../frontend'
Write-Host '  npm run build'
