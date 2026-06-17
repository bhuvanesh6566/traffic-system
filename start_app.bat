@echo off
title Smart Traffic - Web App
color 0B
echo ============================================
echo   Smart Traffic Control System - Web App
echo ============================================
echo.
echo Starting Flask app on http://localhost:5000
echo Press Ctrl+C to stop.
echo.

cd /d "%~dp0"

:: Open browser after 2 seconds
start /b cmd /c "timeout /t 2 >nul && start http://localhost:5000"

python app.py

echo.
echo [App stopped]
pause
