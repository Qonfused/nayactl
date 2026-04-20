@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
  "%SCRIPT_DIR%.venv\Scripts\python.exe" -B -m nayactl %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 -B -m nayactl %*
  exit /b %ERRORLEVEL%
)

python -B -m nayactl %*
exit /b %ERRORLEVEL%
