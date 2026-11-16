@echo off
rem NextBurn setup for Windows: finds Python 3.9 or later and runs setup_nextburn.py.
rem Usage: setup.cmd [--serve] [--pull] [--full] [--no-run] [--no-venv] [--no-open]
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 setup_nextburn.py %*
  exit /b
)
where python >nul 2>nul
if not errorlevel 1 (
  python setup_nextburn.py %*
  exit /b
)
echo NextBurn needs Python 3.9 or later. Install it from https://www.python.org/downloads/ and run this again.
exit /b 1
