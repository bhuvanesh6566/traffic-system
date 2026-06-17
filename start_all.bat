@echo off
title Smart Traffic - Full System (Single Machine)
color 0A
echo ============================================
echo   Smart Traffic - Launch All (1 Machine)
echo   Opens broker, app and simulation
echo   in separate windows for local testing
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] Starting Broker...
start "Broker" cmd /k "color 0E && title Broker && python broker.py"
timeout /t 2 >nul

echo [2/3] Starting Web App...
start "Web App" cmd /k "color 0B && title Web App && python app.py"
timeout /t 3 >nul

echo [3/3] Starting Simulation...
start "Simulation" cmd /k "color 0C && title Simulation && python simulate.py"
timeout /t 2 >nul

echo.
echo [Opening browser...]
start http://localhost:5000

echo.
echo All components started in separate windows.
echo Close each window individually to stop them.
echo.
pause
