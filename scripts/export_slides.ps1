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

Remove-Item $slidesPdf -ErrorAction SilentlyContinue
Write-Host "Rendering PDF..." -ForegroundColor Yellow
$profileDir = Join-Path $env:TEMP "control-layer-slides-export"
& $browserPath --headless --disable-gpu --user-data-dir="$profileDir" `
    --print-to-pdf="$slidesPdf" `
    --no-pdf-header-footer `
    "$fileUrl" 2>&1 | Out-Null

# The browser launcher can return before the renderer finishes writing; wait for a stable file.
$deadline = (Get-Date).AddSeconds(90)
$lastSize = -1
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
    if (Test-Path $slidesPdf) {
        $size = (Get-Item $slidesPdf).Length
        if ($size -gt 0 -and $size -eq $lastSize) { break }
        $lastSize = $size
    }
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
