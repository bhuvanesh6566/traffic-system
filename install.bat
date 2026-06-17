@echo off
title Installing Traffic System Dependencies
color 0A
echo ============================================
echo   Smart Traffic Control System - Setup
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo [OK] Python found:
python --version
echo.

:: Upgrade pip silently
echo [1/2] Upgrading pip...
python -m pip install --upgrade pip --quiet

:: Install requirements
echo [2/2] Installing packages from requirements.txt...
pip install -r "%~dp0requirements.txt"

if errorlevel 1 (
    echo.
    echo [ERROR] Some packages failed to install. Check the output above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   All dependencies installed successfully!
echo ============================================
echo.
echo You can now run:
echo   start_app.bat        - Launch the web app
echo   start_broker.bat     - Launch the broker (Laptop 1 only)
echo   start_agent.bat      - Launch a junction agent
echo   start_simulate.bat   - Launch simulation (no cameras)
echo.
pause
