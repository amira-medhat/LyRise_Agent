@echo off
echo ========================================
echo Removing Sensitive Files from Git
echo ========================================
echo.
echo This will remove sensitive files from Git tracking
echo but KEEP them on your local machine.
echo.
pause

cd /d "%~dp0"

echo.
echo Removing .env files...
git rm --cached -r */.env 2>nul
git rm --cached .env 2>nul

echo.
echo Removing credentials...
git rm --cached -r */credentials/ 2>nul
git rm --cached -r */*-credentials.json 2>nul
git rm --cached -r */token.pickle 2>nul
git rm --cached -r */token.json 2>nul

echo.
echo Removing database files...
git rm --cached -r */database/*.db 2>nul
git rm --cached -r */database/*.xlsx 2>nul
git rm --cached -r */*.db 2>nul
git rm --cached -r */schedules.db 2>nul
git rm --cached -r */schedules.xlsx 2>nul

echo.
echo Removing audio files...
git rm --cached -r */*.wav 2>nul
git rm --cached -r */*.mp3 2>nul
git rm --cached -r */*.ogg 2>nul
git rm --cached -r */*.webm 2>nul

echo.
echo ========================================
echo Done! Now commit the changes:
echo.
echo   git commit -m "Remove sensitive files from tracking"
echo   git push
echo.
echo Your local files are safe!
echo ========================================
pause
