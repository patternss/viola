# Viola ChatBot Startup Script
# This script starts the Viola server using Anaconda Python

Write-Host "Starting Viola ChatBot..." -ForegroundColor Green
Write-Host "Using Anaconda Python environment" -ForegroundColor Yellow

# Change to project directory
Set-Location "C:\Users\jaakk\Desktop\Kuviola\viola"

# Start the server using Anaconda Python
& "C:\ProgramData\anaconda3\python.exe" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

Write-Host "Server stopped." -ForegroundColor Red
