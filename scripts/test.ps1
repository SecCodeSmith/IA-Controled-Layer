# Test script for AI Control Layer
# Runs pytest, ruff linting, and npm tests

$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# Resolve repo root
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "=== AI Control Layer Test Suite ===" -ForegroundColor Cyan

$testsFailed = $false

# 1. Backend pytest
Write-Host "`n[1/3] Running Backend pytest..." -ForegroundColor Yellow
Push-Location Backend
python -m pytest -q --cov=control_layer --cov-report=term-missing
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ pytest failed" -ForegroundColor Red
    $testsFailed = $true
} else {
    Write-Host "  ✓ pytest passed" -ForegroundColor Green
}
Pop-Location

# 2. Backend ruff
Write-Host "`n[2/3] Running Backend ruff check..." -ForegroundColor Yellow
Push-Location Backend
python -m ruff check src tests
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ ruff check failed" -ForegroundColor Red
    $testsFailed = $true
} else {
    Write-Host "  ✓ ruff check passed" -ForegroundColor Green
}
Pop-Location

# 3. Frontend npm test
Write-Host "`n[3/3] Running Frontend tests..." -ForegroundColor Yellow
Push-Location Frontent
npm test -- --run
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ npm tests failed" -ForegroundColor Red
    $testsFailed = $true
} else {
    Write-Host "  ✓ npm tests passed" -ForegroundColor Green
}
Pop-Location

# Summary
Write-Host "`n=== Test Summary ===" -ForegroundColor Cyan
if ($testsFailed) {
    Write-Host "Some tests failed!" -ForegroundColor Red
    exit 1
} else {
    Write-Host "All tests passed!" -ForegroundColor Green
    exit 0
}
