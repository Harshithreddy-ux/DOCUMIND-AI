@echo off
TITLE DocuMind AI - Orchestrator Launcher

echo ======================================================
echo    DOCUMIND AI - Autonomous Document Intelligence
echo ======================================================
echo.

echo [1/4] Starting Docker Containers (PostgreSQL + Neo4j)...
docker-compose up -d

echo.
echo Waiting 5 seconds for databases to initialize...
timeout /t 5 /nobreak > nul

echo.
echo [2/4] Launching FastAPI Backend (Port 8000)...
start "DocuMind - FastAPI Backend" cmd /k "uvicorn main:app --reload --port 8000"

echo.
echo Waiting 5 seconds for FastAPI server to start...
timeout /t 5 /nobreak > nul

echo.
echo [3/4] Launching Streamlit Dashboard (Port 8501)...
start "DocuMind - Streamlit Dashboard" cmd /k "python -m streamlit run app.py"

echo.
echo [4/4] Launching Cloudflare Tunnel (Port 8000 Webhook Exposer)...
where cloudflared >nul 2>nul
if %errorlevel%==0 (
    start "DocuMind - Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://localhost:8000"
) else (
    echo [NOTE] Cloudflare CLI (cloudflared) not found on PATH. Skipping tunnel window.
)

echo.
echo ======================================================
echo    DocuMind AI Stack Launch Initiated!
echo ======================================================
echo    - Streamlit Dashboard: http://localhost:8501
echo    - FastAPI Gateway:     http://localhost:8000
echo    - Interactive API Docs:http://localhost:8000/docs
echo    - Neo4j Browser:       http://localhost:7474
echo ======================================================
echo.
pause
