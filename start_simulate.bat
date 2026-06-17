@echo off
title Smart Traffic - Simulation (No Cameras)
color 0C
echo ============================================
echo   Smart Traffic Control System - Simulate
echo   Simulates 4 junctions without cameras
echo ============================================
echo.
echo Make sure broker.py is already running on Laptop 1.
echo This script sends fake vehicle data for all 4 junctions.
echo Press Ctrl+C to stop.
echo.

cd /d "%~dp0"
python simulate.py

echo.
echo [Simulation stopped]
pause
