# One-Command Launcher for Fintech Agent (Backend + Frontend)
param([int]$BackendPort=5050,[int]$FrontendPort=8501)

Write-Host "============================================"
Write-Host "Starting Fintech Conversational Agent..."
Write-Host "Backend  -> http://127.0.0.1:$BackendPort"
Write-Host "Frontend -> http://127.0.0.1:$FrontendPort"
Write-Host "============================================"

if (!(Test-Path ".venv")) { 
    python -m venv .venv 
}
& .\.venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt

# Load environment variables from .env
if (Test-Path ".env") {
    (Get-Content .env) | ForEach-Object {
        if ($_ -match "=") {
            $k, $v = $_.Split("=",2)
            ${env:$k} = $v
        }
    }
    Write-Host "OPENAI_API_KEY loaded from .env (session only)"
}

# Start backend
Write-Host "Launching Backend (FastAPI)..."
Start-Process -FilePath python -ArgumentList "-m","uvicorn","backend.app:app","--reload","--port",$BackendPort

Start-Sleep -Seconds 4

# Start frontend
Write-Host "Launching Frontend (Streamlit)..."
Start-Process -FilePath streamlit -ArgumentList "run","frontend/chat_ui.py","--server.port",$FrontendPort

Write-Host ""
Write-Host "All systems running!"
Write-Host "Open your browser at http://localhost:$FrontendPort"
