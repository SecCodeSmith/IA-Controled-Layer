# Lint script for AI Control Layer
# Runs ruff check and npm lint

$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# Resolve repo root
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "=== AI Control Layer Lint ===" -ForegroundColor Cyan

$lintFailed = $false

# 1. Backend ruff
Write-Host "`n[1/2] Running Backend ruff check..." -ForegroundColor Yellow
Push-Location Backend
python -m ruff check src tests
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ ruff check failed" -ForegroundColor Red
    $lintFailed = $true
} else {
    Write-Host "  ✓ ruff check passed" -ForegroundColor Green
}
Pop-Location

# 2. Frontend npm lint
Write-Host "`n[2/2] Running Frontend lint..." -ForegroundColor Yellow
Push-Location Frontent
npm run lint
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ npm lint failed" -ForegroundColor Red
    $lintFailed = $true
} else {
    Write-Host "  ✓ npm lint passed" -ForegroundColor Green
}
Pop-Location

# Summary
Write-Host "`n=== Lint Summary ===" -ForegroundColor Cyan
if ($lintFailed) {
    Write-Host "Linting issues found!" -ForegroundColor Red
    exit 1
} else {
    Write-Host "All linting passed!" -ForegroundColor Green
    exit 0
}
