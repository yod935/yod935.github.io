@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo Starting local HTTP server for Product Catalog...
echo.
echo After the server starts, open:
echo   http://localhost:8080/index.html
echo.
echo Press Ctrl+C to stop the server.
echo.

REM Try to open browser automatically
start "" "http://localhost:8080/index.html" 2>nul

REM Try managed Python first, then system Python as fallback
set PYTHON_EXE=
if exist "C:\Users\May\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
    set PYTHON_EXE=C:\Users\May\.workbuddy\binaries\python\versions\3.13.12\python.exe
) else (
    where python >nul 2>nul && set PYTHON_EXE=python || echo ERROR: Python not found! && pause && exit /b
)
%PYTHON_EXE% -m http.server 8080
