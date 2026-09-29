# Boost Rankers — AI Search RewriteRequest production fix
# Scope: ONLY backend\ai_search_optimization.py

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$file = Join-Path $root "backend\ai_search_optimization.py"

if (-not (Test-Path -LiteralPath $file)) {
    throw "Missing file: $file"
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$file.bak.$stamp"
Copy-Item -LiteralPath $file -Destination $backup -Force

try {
    $content = Get-Content -LiteralPath $file -Raw -Encoding UTF8

    # Add the missing field specifically inside RewriteRequest.
    $classPattern = '(?s)(class RewriteRequest\(BaseModel\):.*?)(?=\nclass |\Z)'
    $match = [regex]::Match($content, $classPattern)

    if (-not $match.Success) {
        throw "Could not locate RewriteRequest class."
    }

    $classBody = $match.Value

    if ($classBody -notmatch '(?m)^\s+used_focus_keywords:\s*list\[str\]') {
        $analysisPattern = '(?m)^(\s+analysis:\s*dict\[str,\s*Any\].*)$'
        if ($classBody -notmatch $analysisPattern) {
            throw "RewriteRequest was found, but its analysis field was not found."
        }

        $classBody = [regex]::Replace(
            $classBody,
            $analysisPattern,
            '$1' + "`n" + '    used_focus_keywords: list[str] = Field(default_factory=list, max_length=500)',
            1
        )

        $content = $content.Substring(0, $match.Index) +
                   $classBody +
                   $content.Substring($match.Index + $match.Length)
    }

    Set-Content -LiteralPath $file -Value $content -Encoding UTF8

    # Verify the field is actually inside RewriteRequest.
    $verify = Get-Content -LiteralPath $file -Raw -Encoding UTF8
    $verifyMatch = [regex]::Match($verify, $classPattern)

    if (-not $verifyMatch.Success) {
        throw "Verification failed: RewriteRequest could not be read back."
    }

    if ($verifyMatch.Value -notmatch '(?m)^\s+used_focus_keywords:\s*list\[str\]\s*=\s*Field\(default_factory=list,\s*max_length=500\)') {
        throw "Verification failed: used_focus_keywords is not inside RewriteRequest."
    }

    # Compile exact file.
    & python -m py_compile $file
    if ($LASTEXITCODE -ne 0) {
        throw "Python compilation failed."
    }

    Write-Host ""
    Write-Host "SUCCESS - AI Search RewriteRequest fixed." -ForegroundColor Green
    Write-Host ""
    Write-Host "Modified ONLY:" -ForegroundColor Cyan
    Write-Host "  backend\ai_search_optimization.py"
    Write-Host ""
    Write-Host "Backup:" -ForegroundColor Yellow
    Write-Host "  $backup"
    Write-Host ""
    Write-Host "Next:"
    Write-Host "  1. Restart/redeploy Uvicorn."
    Write-Host "  2. Test Analyze Post."
    Write-Host '  3. Test "Rewrite & Optimize".'
    Write-Host "  4. If successful, commit only backend\ai_search_optimization.py."
}
catch {
    Copy-Item -LiteralPath $backup -Destination $file -Force
    Write-Host ""
    Write-Host "PATCH FAILED - original file restored." -ForegroundColor Red
    throw
}
