# EduTrack Zero-Config Setup & Launch Script
# This script initializes the backend and frontend for local development.

$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param(
        [scriptblock]$Command,
        [string]$FailureMessage
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

Write-Host "--- 🚀 Launching EduTrack Integrated Local Setup ---" -ForegroundColor Cyan

# 1. Backend Setup
Write-Host "`n[1/4] Preparing Backend..." -ForegroundColor Yellow
$repoRoot = Get-Location
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Virtual environment not found at root. Creating one..."
    & python -m venv (Join-Path $repoRoot ".venv")
}

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    $dockerExe = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (-not (Test-Path $dockerExe)) {
        throw "Docker is required for PostgreSQL-only local development. Install Docker Desktop and re-run setup_dev.ps1."
    }
    $docker = @{ Source = $dockerExe }
}

Write-Host "Starting PostgreSQL, Redis, and Ollama via Docker Compose..."
Invoke-CheckedCommand { & $docker.Source compose up -d db redis ollama } "Docker Compose startup failed."

Set-Location "backend"

Write-Host "Installing dependencies..."
Invoke-CheckedCommand { & $python -m pip install -r requirements.txt } "Backend dependency installation failed."

Write-Host "Applying PostgreSQL migrations..."
Invoke-CheckedCommand { & $python -m alembic upgrade head } "Database migrations failed."

Write-Host "Bootstrapping development data..."
Invoke-CheckedCommand { & $python scripts\bootstrap_dev_db.py } "Development data bootstrap failed."

Set-Location ".."

# 2. Frontend Setup
Write-Host "`n[2/4] Preparing Frontend..." -ForegroundColor Yellow
Set-Location "web_frontend"

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..."
    Invoke-CheckedCommand { & npm install } "Frontend dependency installation failed."
}

Set-Location ".."

# 3. Launch Services
Write-Host "`n[3/4] Launching Frontend & Backend..." -ForegroundColor Yellow
Write-Host "Backend: http://localhost:8000" -ForegroundColor Gray
Write-Host "Frontend: http://localhost:8080 (or next available port)" -ForegroundColor Gray
Write-Host "PostgreSQL: localhost:5433" -ForegroundColor Gray
Write-Host "Redis: localhost:6380" -ForegroundColor Gray

# Start Backend in a new window
Start-Process powershell.exe -ArgumentList "-NoExit -Command cd backend; ..\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"

# Start Frontend in current session or new window
Start-Process powershell.exe -ArgumentList "-NoExit -Command cd web_frontend; npm run dev"

Write-Host "`n[4/4] Setup Complete!" -ForegroundColor Green
Write-Host "Services are initializing in separate windows. Please wait a few seconds before refreshing."
