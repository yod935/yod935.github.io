@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================
echo   YOD Product Catalog - Local Server
echo ========================================
echo.

REM Kill any python http.server processes that might be blocking port 8080
echo Cleaning up old server processes...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8080 "') do (
    taskkill /F /PID %%a >nul 2>nul
)
timeout /t 1 /nobreak > nul

REM Try managed Python first, then system Python as fallback
set PYTHON_EXE=
if exist "C:\Users\May\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
    set PYTHON_EXE=C:\Users\May\.workbuddy\binaries\python\versions\3.13.12\python.exe
) else (
    where python >nul 2>nul && set PYTHON_EXE=python
)

if "%PYTHON_EXE%"=="" (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

echo Starting server on port 8080...
echo.
echo Open in browser: http://localhost:8080/index.html
echo.
echo Press Ctrl+C to stop the server.
echo.

REM Open browser after 1 second delay
start "" cmd /c "timeout /t 1 /nobreak > nul && start http://localhost:8080/index.html"

%PYTHON_EXE% -m http.server 8080
