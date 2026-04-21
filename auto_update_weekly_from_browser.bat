@echo off
cd /d "%~dp0"
python "%~dp0auto_update_weekly_from_firefox.py"
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
call "%~dp0auto_push_weekly_to_github.bat"
