@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m app.main
if errorlevel 1 pause
