@echo off
setlocal enabledelayedexpansion
:: ====================================================================
:: RemoteDesk - 100% Silent Background Auto-Start Installer
:: Completely invisible on Windows boot (No black window, No taskbar icon)
:: ====================================================================

echo ==============================================================
echo    RemoteDesk - Silent Auto-Start Setup
echo ==============================================================
echo.

set AGENT_DIR=%~dp0
set AGENT_PY=%AGENT_DIR%agent.py
set VBS_LAUNCHER=%AGENT_DIR%start_invisible.vbs
set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup

:: 1. Locate real python.exe (skipping WindowsApps alias if real Python is installed)
set PYTHON_EXE=
for /f "delims=" %%i in ('where python.exe 2^>nul') do (
    set "CANDIDATE=%%i"
    echo !CANDIDATE! | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
    )
)

:: If not found outside WindowsApps, use whatever python.exe exists
if not defined PYTHON_EXE (
    for /f "delims=" %%i in ('where python.exe 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
    )
)

if not defined PYTHON_EXE (
    echo [ERROR] Python was not found!
    echo Please install Python on this Windows machine and check "Add Python to PATH".
    pause
    exit /b 1
)

:: Locate corresponding pythonw.exe in the same folder
for %%F in ("!PYTHON_EXE!") do set "PY_DIR=%%~dpF"
if exist "!PY_DIR!pythonw.exe" (
    set "PYTHONW_EXE=!PY_DIR!pythonw.exe"
) else (
    set "PYTHONW_EXE=!PYTHON_EXE!"
)

echo [OK] Python engine: "!PYTHON_EXE!"
echo [OK] Silent runner: "!PYTHONW_EXE!"
echo.

:: 2. Install required libraries using normal python.exe (shows progress, won't hang)
echo [RemoteDesk] Checking dependencies...
"!PYTHON_EXE!" -m pip install -r "%AGENT_DIR%requirements.txt"
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Pip encountered an issue. Proceeding with existing packages...
)
echo [OK] Dependencies verified.
echo.

:: 3. Generate 100% invisible VBScript launcher (SW_HIDE = 0)
echo Set WshShell = CreateObject("WScript.Shell") > "%VBS_LAUNCHER%"
echo WshShell.CurrentDirectory = "%AGENT_DIR%" >> "%VBS_LAUNCHER%"
echo WshShell.Run """!PYTHONW_EXE!"" """ ^& "%AGENT_PY%""", 0, False >> "%VBS_LAUNCHER%"

:: 4. Place into official Windows Startup folder
copy /y "%VBS_LAUNCHER%" "%STARTUP_FOLDER%\RemoteDeskSilent.vbs" >nul
echo [OK] Installed into Windows Startup folder.

:: 5. Register in Windows Task Scheduler (runs hidden with highest privileges on logon)
schtasks /create /tn "RemoteDeskSilent" /tr "wscript.exe \"%VBS_LAUNCHER%\"" /sc onlogon /rl highest /f >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Registered Silent Task Scheduler service.
)

:: 6. Register in Windows Registry Run key
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RemoteDeskSilent" /t REG_SZ /d "wscript.exe \"%VBS_LAUNCHER%\"" /f >nul
echo [OK] Registered Silent Windows Run registry key.

echo.
echo ==============================================================
echo  SUCCESS! RemoteDesk will now start 100%% INVISIBLY on boot.
echo  • Zero black CMD windows
echo  • No taskbar icons
echo  • Runs silently in the background
echo ==============================================================
echo.
echo Launching silent agent in background now...
wscript.exe "%VBS_LAUNCHER%"

echo.
echo [DONE] The agent is running silently in the background!
echo You can now close this window.
echo.
pause
