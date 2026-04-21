@echo off
setlocal
cd /d "%~dp0"

git diff --quiet -- leaderboard_7_days.json weekly_source.json
if %ERRORLEVEL% EQU 0 (
  echo No weekly leaderboard changes to push.
  exit /b 0
)

git add leaderboard_7_days.json weekly_source.json
git commit -m "Update weekly leaderboard"
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

git push
exit /b %ERRORLEVEL%
