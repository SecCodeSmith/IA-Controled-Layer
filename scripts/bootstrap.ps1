# Bootstrap script for AI Control Layer
# Sets up Python environment, Node modules, ML classifier, and Ollama model

$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:CTRL_OLLAMA_MODEL = $env:CTRL_OLLAMA_MODEL -or "qwen2.5:7b"

# Resolve repo root
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "=== AI Control Layer Bootstrap ===" -ForegroundColor Cyan

$skipped = @()

# 1. Backend Python setup
Write-Host "`n[1/4] Setting up Backend Python environment..." -ForegroundColor Yellow
Push-Location Backend
python -m pip install -e ".[dev]" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ Backend pip install failed" -ForegroundColor Red
    $skipped += "Backend pip install"
} else {
    Write-Host "  ✓ Backend dependencies installed" -ForegroundColor Green
}
Pop-Location

# 2. Frontend npm setup
Write-Host "`n[2/4] Setting up Frontend Node modules..." -ForegroundColor Yellow
Push-Location Frontent
if (Test-Path package-lock.json) {
    npm ci 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ✗ Frontend npm ci failed" -ForegroundColor Red
        $skipped += "Frontend npm setup"
    } else {
        Write-Host "  ✓ Frontend dependencies installed (npm ci)" -ForegroundColor Green
    }
} else {
    npm install 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ✗ Frontend npm install failed" -ForegroundColor Red
        $skipped += "Frontend npm setup"
    } else {
        Write-Host "  ✓ Frontend dependencies installed (npm install)" -ForegroundColor Green
    }
}
Pop-Location

# 3. Train ML classifier
Write-Host "`n[3/4] Training ML classifier..." -ForegroundColor Yellow
Push-Location Backend
python -m control_layer.ml.train `
    --dataset "src/control_layer/ml/dataset/prompt_injection_dataset.csv" `
    --out "src/control_layer/ml/artifacts/prompt_injection_classifier.joblib" `
    --model logreg 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ ML classifier training failed" -ForegroundColor Red
    $skipped += "ML classifier training"
} else {
    Write-Host "  ✓ ML classifier trained" -ForegroundColor Green
}
Pop-Location

# 4. Ollama setup
Write-Host "`n[4/4] Setting up Ollama..." -ForegroundColor Yellow
$ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaCmd) {
    Write-Host "  Pulling Ollama model: $($env:CTRL_OLLAMA_MODEL)..." -ForegroundColor Cyan
    ollama pull $env:CTRL_OLLAMA_MODEL 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ⚠ Ollama pull failed (not critical)" -ForegroundColor Yellow
        $skipped += "Ollama setup"
    } else {
        Write-Host "  ✓ Ollama model pulled" -ForegroundColor Green

        Write-Host "  Running warm-up completion..." -ForegroundColor Cyan
        $warmupPayload = @{
            model = $env:CTRL_OLLAMA_MODEL
            messages = @(@{role = "user"; content = "OK"})
            stream = $false
        } | ConvertTo-Json

        $response = Invoke-WebRequest -Uri "http://localhost:11434/v1/chat/completions" `
            -Method POST -Body $warmupPayload -ContentType "application/json" `
            -ErrorAction SilentlyContinue
        Write-Host "  ✓ Ollama warm-up completed" -ForegroundColor Green
    }
} else {
    Write-Host "  ⚠ ollama not found on PATH, skipping model pull" -ForegroundColor Yellow
    $skipped += "Ollama setup"
}

# Summary
Write-Host "`n=== Bootstrap Complete ===" -ForegroundColor Green
if ($skipped.Count -gt 0) {
    Write-Host "Skipped steps:" -ForegroundColor Yellow
    $skipped | ForEach-Object { Write-Host "  • $_" }
}
Write-Host "Ready to run: ./scripts/run_dev.ps1" -ForegroundColor Cyan
