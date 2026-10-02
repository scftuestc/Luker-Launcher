@echo off
cd /d "%~dp0"
echo Building...
pyinstaller launcher.spec --noconfirm --distpath .
rd /s /q build 2>nul
rd /s /q dist 2>nul
echo Done!
pause
