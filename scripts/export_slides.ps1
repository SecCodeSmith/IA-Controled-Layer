# Export slides script for AI Control Layer
# Renders presentation/slides.html to PDF using Edge or Chrome

$ErrorActionPreference = "Continue"

# Resolve repo root
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "=== AI Control Layer Slides Export ===" -ForegroundColor Cyan

# Resolve absolute paths
$slidesHtml = (Resolve-Path "presentation/slides.html").Path
$slidesPdf = (Resolve-Path "presentation").Path + "\slides.pdf"

Write-Host "Source: $slidesHtml" -ForegroundColor Cyan
Write-Host "Output: $slidesPdf" -ForegroundColor Cyan

# Try Edge first
$edgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$chromeAltPath = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

$browserPath = $null

if (Test-Path $edgePath) {
    $browserPath = $edgePath
    Write-Host "Using: Microsoft Edge" -ForegroundColor Green
} elseif (Test-Path $chromePath) {
    $browserPath = $chromePath
    Write-Host "Using: Google Chrome" -ForegroundColor Green
} elseif (Test-Path $chromeAltPath) {
    $browserPath = $chromeAltPath
    Write-Host "Using: Google Chrome (x86)" -ForegroundColor Green
} else {
    Write-Host "Error: Neither Edge nor Chrome found!" -ForegroundColor Red
    exit 1
}

# Convert path to file:/// URL
$fileUrl = "file:///$($slidesHtml -replace '\\', '/')"

Write-Host "Rendering PDF..." -ForegroundColor Yellow
& $browserPath --headless --disable-gpu `
    --print-to-pdf="$slidesPdf" `
    --no-pdf-header-footer `
    "$fileUrl"

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ PDF export failed (browser error)" -ForegroundColor Red
    exit $LASTEXITCODE
}

if (Test-Path $slidesPdf) {
    $fileSize = (Get-Item $slidesPdf).Length / 1MB
    Write-Host "✓ PDF exported successfully" -ForegroundColor Green
    Write-Host "  File: $slidesPdf" -ForegroundColor Cyan
    Write-Host "  Size: $([Math]::Round($fileSize, 2)) MB" -ForegroundColor Cyan
} else {
    Write-Host "✗ PDF export failed (file not created)" -ForegroundColor Red
    exit 1
}
