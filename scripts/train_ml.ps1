# Train ML classifier script for AI Control Layer
# Trains the prompt injection classifier with optional pass-through arguments

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Args
)

$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# Resolve repo root
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "=== AI Control Layer ML Training ===" -ForegroundColor Cyan

Push-Location Backend
Write-Host "Training logistic regression classifier..." -ForegroundColor Yellow

$cmd = @(
    "python", "-m", "control_layer.ml.train",
    "--dataset", "src/control_layer/ml/dataset/prompt_injection_dataset.csv",
    "--out", "src/control_layer/ml/artifacts/prompt_injection_classifier.joblib",
    "--extra", "src/control_layer/ml/dataset/security_education.csv",
    "--model", "logreg"
)

# Add any additional arguments
if ($Args.Count -gt 0) {
    $cmd += $Args
}

& $cmd[0] $cmd[1..($cmd.Length-1)]
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Logistic regression training failed" -ForegroundColor Red
    Pop-Location
    exit $LASTEXITCODE
}

Write-Host "✓ Logistic regression training complete" -ForegroundColor Green

Write-Host "Training decision tree classifier with benign supplement..." -ForegroundColor Yellow

$cmd = @(
    "python", "-m", "control_layer.ml.train",
    "--dataset", "src/control_layer/ml/dataset/prompt_injection_dataset.csv",
    "--extra", "src/control_layer/ml/dataset/benign_operational.csv",
    "--out", "src/control_layer/ml/artifacts/prompt_injection_tree.joblib",
    "--model", "tree"
)

# Add any additional arguments
if ($Args.Count -gt 0) {
    $cmd += $Args
}

& $cmd[0] $cmd[1..($cmd.Length-1)]
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Decision tree training failed" -ForegroundColor Red
    Pop-Location
    exit $LASTEXITCODE
}

Write-Host "✓ Decision tree training complete" -ForegroundColor Green
Pop-Location
