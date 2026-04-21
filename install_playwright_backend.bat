@echo off
cd /d "%~dp0"

echo Installing Playwright Python package...
python -m pip install playwright
if errorlevel 1 goto :error

echo Installing Playwright Chromium browser...
python -m playwright install chromium
if errorlevel 1 goto :error

echo.
echo Playwright backend install complete.
echo You can now run start_server.bat or python server.py
goto :eof

:error
echo.
echo Playwright install failed.
exit /b 1
