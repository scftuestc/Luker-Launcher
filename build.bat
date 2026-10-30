@echo off
cd /d "%~dp0"
echo Building...
call pyinstaller launcher.spec --noconfirm --distpath .
if errorlevel 1 goto fail
rd /s /q build 2>nul
echo Done!
pause
exit /b 0

:fail
echo Build failed. The existing exe was not replaced.
pause
exit /b 1
