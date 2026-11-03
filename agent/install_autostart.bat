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

:: 1. Locate pythonw.exe (Windowless Python runner)
for /f "delims=" %%i in ('where pythonw.exe 2^>nul') do set PYTHONW_PATH=%%i

if "%PYTHONW_PATH%"=="" (
    for /f "delims=" %%i in ('where python.exe 2^>nul') do (
        set PY_DIR=%%~dpi
        if exist "!PY_DIR!pythonw.exe" (
            set PYTHONW_PATH=!PY_DIR!pythonw.exe
        )
    )
)

if "%PYTHONW_PATH%"=="" (
    echo [ERROR] Python was not found!
    echo Please install Python on this Windows machine and check "Add Python to PATH".
    pause
    exit /b 1
)

echo [OK] Found Silent Python at: "%PYTHONW_PATH%"

:: 2. Install required libraries
echo [RemoteDesk] Verifying dependencies...
"%PYTHONW_PATH%" -m pip install -r "%AGENT_DIR%requirements.txt" >nul 2>&1

:: 3. Generate 100% invisible VBScript launcher (NO black window, NO taskbar icon)
:: Uses SW_HIDE (0) and sets working directory directly in memory
echo Set WshShell = CreateObject("WScript.Shell") > "%VBS_LAUNCHER%"
echo WshShell.CurrentDirectory = "%AGENT_DIR%" >> "%VBS_LAUNCHER%"
echo WshShell.Run """%PYTHONW_PATH%"" """ ^& "%AGENT_PY%""", 0, False >> "%VBS_LAUNCHER%"

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
echo Launching silent agent right now...
wscript.exe "%VBS_LAUNCHER%"

echo Done. You can close this window.
pause
