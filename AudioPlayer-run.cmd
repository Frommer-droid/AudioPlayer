@echo off
cd /d "%~dp0"
chcp 65001 >nul
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
  echo Не найдено окружение .venv. См. USAGE.md.
  pause
  exit /b 1
)
if not exist "%~dp0AudioPlayer.py" (
  echo Не найден AudioPlayer.py.
  pause
  exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0AudioPlayer.py" %*
