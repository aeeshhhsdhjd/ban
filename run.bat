@echo off
title Telegram Report Bot
echo ================================
echo    Telegram Report Bot System
echo ================================
echo.
echo Starting all modules...
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found!
    echo Please install Python 3.10+
    pause
    exit /b 1
)

REM Run setup if first time
if not exist "configs\config.json" (
    echo ⚙️ First time setup detected...
    python setup.py
    if errorlevel 1 (
        echo ❌ Setup failed!
        pause
        exit /b 1
    )
)

REM Run main system
echo 🚀 Starting bot system...
python main.py

if errorlevel 1 (
    echo ❌ Bot crashed!
    echo Check logs for details.
    pause
)
