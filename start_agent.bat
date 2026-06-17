@echo off
title Smart Traffic - Junction Agent
color 0D
echo ============================================
echo   Smart Traffic Control System - Agent
echo ============================================
echo.
echo Which junction is this laptop?
echo   A = Laptop 1    B = Laptop 2
echo   C = Laptop 3    D = Laptop 4
echo.
set /p JID="Enter Junction ID (A/B/C/D): "

:: Validate input
if /i "%JID%"=="A" goto valid
if /i "%JID%"=="B" goto valid
if /i "%JID%"=="C" goto valid
if /i "%JID%"=="D" goto valid

echo [ERROR] Invalid junction ID. Must be A, B, C or D.
pause
exit /b 1

:valid
echo.
echo [INFO] Setting Junction ID to %JID% in config.py ...

:: Patch JUNCTION_ID in config.py using Python one-liner
python -c ^
"import re, sys; ^
path=r'%~dp0config.py'; ^
txt=open(path).read(); ^
txt=re.sub(r'JUNCTION_ID\s*=\s*\"[A-D]\"', 'JUNCTION_ID = \"%JID%\"', txt); ^
open(path,'w').write(txt); ^
print('[OK] config.py updated: JUNCTION_ID =', \"%JID%\")"

echo.
echo Starting agent for Junction %JID%...
echo Press Ctrl+C to stop.
echo.

cd /d "%~dp0"
python agent.py

echo.
echo [Agent stopped]
pause
