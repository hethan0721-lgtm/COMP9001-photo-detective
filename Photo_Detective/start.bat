@echo off
setlocal
cd /d "%~dp0"
python main.py
if errorlevel 1 (
  echo.
  echo Could not start Photo Detective.
  echo Please install Python 3.8+ from python.org, then try again.
  pause
)
