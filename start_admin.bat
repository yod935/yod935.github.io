@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo Starting YOD Catalog Admin Panel...
echo.
echo ============================================================
echo   Admin panel will open at http://localhost:8888
echo ============================================================
echo.

REM Kill any process still holding port 8888 from a previous run
echo Cleaning up old admin processes...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8888 "') do (
    taskkill /F /PID %%a >nul 2>nul
)
timeout /t 1 /nobreak > nul

REM Open the browser after a short delay so the server has time to start
start "" cmd /c "timeout /t 2 /nobreak > nul && start http://localhost:8888"

echo Starting server on port 8888...
echo.
C:\Users\May\.workbuddy\binaries\python\envs\default\Scripts\python admin.py

pause
