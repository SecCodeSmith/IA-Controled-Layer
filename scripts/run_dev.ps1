# Development server runner for AI Control Layer
# Starts control layer, demo agent, and frontend in separate processes

$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# Resolve repo root
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "=== AI Control Layer Development Servers ===" -ForegroundColor Cyan

# Track child processes
$childProcesses = @()

function Cleanup {
    Write-Host "`nCleaning up processes..." -ForegroundColor Yellow
    foreach ($proc in $childProcesses) {
        try {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            Write-Host "  Stopped process $($proc.Id)"
        } catch {
            # Process already stopped
        }
    }
    exit 0
}

# Start Control Layer (port 8080)
Write-Host "`n[1/3] Starting Control Layer on :8080..." -ForegroundColor Yellow
$proc1 = Start-Process -PassThru -NoNewWindow -FilePath "python" -ArgumentList @(
    "-m", "uvicorn", "control_layer.presentation.main:app",
    "--host", "0.0.0.0", "--port", "8080", "--workers", "1"
) -WorkingDirectory "Backend"
$childProcesses += $proc1
Write-Host "  ✓ Control Layer PID: $($proc1.Id)" -ForegroundColor Green

# Start Demo Agent (port 8090)
Write-Host "`n[2/3] Starting Demo Agent on :8090..." -ForegroundColor Yellow
$proc2 = Start-Process -PassThru -NoNewWindow -FilePath "python" -ArgumentList @(
    "-m", "uvicorn", "demo_agent.main:app", "--port", "8090"
) -WorkingDirectory "Backend"
$childProcesses += $proc2
Write-Host "  ✓ Demo Agent PID: $($proc2.Id)" -ForegroundColor Green

# Start Frontend (port 5173) - use npm.cmd on Windows
Write-Host "`n[3/3] Starting Frontend on :5173..." -ForegroundColor Yellow
$npmCmd = if (Get-Command npm.cmd -ErrorAction SilentlyContinue) { "npm.cmd" } else { "npm" }
$proc3 = Start-Process -PassThru -NoNewWindow -FilePath $npmCmd -ArgumentList "run", "dev" -WorkingDirectory "Frontent"
$childProcesses += $proc3
Write-Host "  ✓ Frontend PID: $($proc3.Id)" -ForegroundColor Green

# Display running URLs
Write-Host "`n=== Running Services ===" -ForegroundColor Green
Write-Host "  Control Layer: http://localhost:8080/health" -ForegroundColor Cyan
Write-Host "  Demo Agent:    http://localhost:8090/agent/health" -ForegroundColor Cyan
Write-Host "  Dashboard:     http://localhost:5173" -ForegroundColor Cyan

Write-Host "`nPress Ctrl+C to stop all services..." -ForegroundColor Yellow

# Block with try/finally to ensure cleanup on Ctrl+C
try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
} finally {
    Cleanup
}
