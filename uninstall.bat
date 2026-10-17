@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Removing startup entry ...
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\StellarisAISteward.bat" 2>nul
echo Removing optional war component (if installed) ...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" tools\install_war_mod.py remove
)
echo Done.
echo.
echo Notes:
echo  - If the panel/brain processes are still running, end pythonw.exe
echo    in Task Manager (or simply reboot).
echo  - The core tool never modifies game files. The optional war
echo    component is removed above; to fully remove, delete this folder.
pause
