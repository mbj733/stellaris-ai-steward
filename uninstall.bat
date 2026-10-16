@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Removing startup entry ...
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\StellarisAISteward.bat" 2>nul
echo Done.
echo.
echo Notes:
echo  - If the panel/brain processes are still running, end pythonw.exe
echo    in Task Manager (or simply reboot).
echo  - This tool never modifies game files; to fully remove,
echo    just delete this folder.
pause
