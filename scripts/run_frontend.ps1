# Check if the backend is running
if (!Test-NetConnection -ComputerName localhost -Port 8000 -InformationLevel Quiet) {
    Write-Host "Backend is not running. Starting backend..."
    Start-Process -FilePath "./scripts/run_backend.ps1"
    Start-Sleep -Seconds 5
}

bun run dev