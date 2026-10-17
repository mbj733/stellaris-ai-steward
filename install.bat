@echo off
chcp 65001 >nul
setlocal
title Stellaris AI Steward - Install
cd /d "%~dp0"

echo ================================================
echo    Stellaris AI Steward  -  Installer
echo    (Chinese guide: see README.md)
echo ================================================
echo.

rem ---- 1) Python check ----
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
    echo [ERROR] Python not found. Install Python 3.10+ first:
    echo         https://www.python.org/downloads/
    echo         - check "Add Python to PATH" during setup
    pause
    exit /b 1
)
for /f "delims=" %%v in ('%PY% --version 2^>^&1') do echo     Found %%v

rem ---- 2) venv ----
if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating virtual environment .venv ...
    %PY% -m venv .venv
    if errorlevel 1 (echo [ERROR] venv creation failed & pause & exit /b 1)
) else (
    echo [1/4] Virtual environment already exists - skip.
)

rem ---- 3) deps ----
echo [2/4] Installing dependencies (psutil / keyboard / capstone / numpy)...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
    echo     Default index failed - retrying with Tsinghua mirror ...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
)
if errorlevel 1 (echo [ERROR] Dependency install failed - check network and rerun. & pause & exit /b 1)

rem ---- 4) autostart (optional; -y = skip for testing) ----
echo [3/4] Add to Windows startup (auto-run with the game)?
if /i "%~1"=="-y" goto noauto
choice /c YN /n /m "      Y=yes (recommended)  N=no : "
if errorlevel 2 goto noauto
set "APPDIR=%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
> "%STARTUP%\StellarisAISteward.bat" echo @echo off
>>"%STARTUP%\StellarisAISteward.bat" echo start "" "%APPDIR%.venv\Scripts\pythonw.exe" "%APPDIR%tools\hai_watch.py"
echo     Startup entry added (remove anytime with uninstall.bat).
goto smoke
:noauto
echo     Startup entry NOT added (rerun installer to change).

:smoke
rem ---- 5) smoke test ----
echo [4/4] Self-test...
echo.
".venv\Scripts\python.exe" tools\selftest_all.py
echo.
if /i "%~1"=="-y" goto war_done
choice /c YN /n /m "Install optional war component (local mod, restart game once)? Y/N : "
if errorlevel 2 goto war_done
".venv\Scripts\python.exe" tools\install_war_mod.py install
echo     War component installed. Restart the game once, then press F9 in the panel.
:war_done
echo.
echo ================================================
echo  Done!
echo   - While the game is running, the steward works automatically
echo     (a small floating panel will appear)
echo   - Manual panel: double-click  start_panel.bat
echo   - Uninstall: double-click  uninstall.bat
echo ================================================
if /i "%~1"=="-y" exit /b 0
pause
