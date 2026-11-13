@echo off
cd /d "%~dp0"
where py >nul 2>nul || (echo Python not found. Install from https://www.python.org/downloads/ and tick "Add to PATH". & pause & exit /b 1)
py -m pip install --quiet --upgrade playwright
py costco_bot.py --check %*
pause
