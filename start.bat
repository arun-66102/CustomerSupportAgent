@echo off
echo ============================================================
echo  Hiver Brand AI Support Agent — Apple Support
echo  Backend: FastAPI + Groq llama-3.3-70b-versatile
echo ============================================================
echo.

cd /d "%~dp0backend"

echo [1/3] Installing dependencies...
pip install -r requirements.txt --quiet

echo [2/3] Starting FastAPI server...
echo.
echo   Backend API : http://localhost:8000
echo   Frontend    : Open frontend/index.html in your browser
echo   API Docs    : http://localhost:8000/docs
echo.
echo [3/3] Startup will process the TWCS dataset on first run (~30s).
echo       Subsequent starts use cached data and are instant.
echo.
echo Press Ctrl+C to stop the server.
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
