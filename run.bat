@echo off
setlocal
rem gtv-debloat launcher for Windows. Double-click to run, or drag/pass args.
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY set "PY=python"
%PY% "%~dp0gtv_debloat.py" %*
pause
