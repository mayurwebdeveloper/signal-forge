@echo off
echo Starting SignalForge backend on :8000 ...
start "SignalForge API" cmd /k "cd /d %~dp0backend && py -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
timeout /t 3 >nul
echo Starting SignalForge frontend on :5173 ...
start "SignalForge UI" cmd /k "cd /d %~dp0frontend && npm run dev"
echo.
echo API:  http://127.0.0.1:8000/docs
echo App:  http://127.0.0.1:5173
echo Login: admin@signalforge.app / Admin@12345
pause
