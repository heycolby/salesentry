@echo off
title Sales Course & Onboarding Hub
cd /d "%~dp0"
echo ===================================================
echo   Starting Sales Course & Gated Onboarding Hub
echo ===================================================
echo.
echo Opening server at http://127.0.0.1:5000
echo.
call venv\Scripts\python.exe app.py
pause
