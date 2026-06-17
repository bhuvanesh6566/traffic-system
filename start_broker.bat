@echo off
title Smart Traffic - Broker (Laptop 1)
color 0E
echo ============================================
echo   Smart Traffic Control System - Broker
echo   Run this ONLY on Laptop 1
echo ============================================
echo.
echo Broker will listen on port 9999.
echo All other laptops must set BROKER_HOST
echo in config.py to this machine's IP address.
echo.

:: Show this machine's IP
echo Your IP addresses:
ipconfig | findstr /i "IPv4"
echo.
echo Press Ctrl+C to stop.
echo.

cd /d "%~dp0"
python broker.py

echo.
echo [Broker stopped]
pause
