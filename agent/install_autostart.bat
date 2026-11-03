@echo off
setlocal enabledelayedexpansion
:: ====================================================================
:: RemoteDesk - Bulletproof Windows Auto-Start Installer
:: Configures the agent to start automatically on Windows startup.
:: ====================================================================

echo ==============================================================
echo    RemoteDesk Windows Auto-Start Setup
echo ==============================================================
echo.

:: 1. Detect exact path of python and pythonw
for /f "delims=" %%i in ('where pythonw.exe 2^>nul') do set PYTHONW_PATH=%%i
if "%PYTHONW_PATH%"=="" (
    for /f "delims=" %%i in ('where python.exe 2^>nul') do set PYTHONW_PATH=%%i
)

if "%PYTHONW_PATH%"=="" (
    echo [ERROR] Python was not found in PATH!
    echo Please install Python and check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [OK] Found Python at: "%PYTHONW_PATH%"

:: 2. Set Directory paths
set AGENT_DIR=%~dp0
set LAUNCHER_BAT=%AGENT_DIR%run_agent.bat
set VBS_SCRIPT=%AGENT_DIR%start_silent.vbs
set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup

echo [RemoteDesk] Installing Python dependencies...
"%PYTHONW_PATH%" -m pip install -r "%AGENT_DIR%requirements.txt"

:: 3. Create run_agent.bat with explicit cd and logging
echo @echo off > "%LAUNCHER_BAT%"
echo cd /d "%AGENT_DIR%" >> "%LAUNCHER_BAT%"
echo "%PYTHONW_PATH%" agent.py ^> "%AGENT_DIR%agent.log" 2^>^&1 >> "%LAUNCHER_BAT%"

:: 4. Create VBS launcher so it runs completely hidden without a black window
echo Set WshShell = CreateObject("WScript.Shell") > "%VBS_SCRIPT%"
echo WshShell.Run """%LAUNCHER_BAT%""", 0, False >> "%VBS_SCRIPT%"

:: 5. Copy silent launcher directly to Windows Startup Folder (Failsafe 1)
copy /y "%VBS_SCRIPT%" "%STARTUP_FOLDER%\RemoteDeskSilent.vbs" >nul
echo [OK] Added to Windows Startup Folder: "%STARTUP_FOLDER%"

:: 6. Register Windows Task Scheduler (Failsafe 2 - runs with highest privileges on logon)
schtasks /create /tn "RemoteDeskAgent" /tr "wscript.exe \"%VBS_SCRIPT%\"" /sc onlogon /rl highest /f >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Registered Scheduled Task "RemoteDeskAgent" with highest privileges.
)

:: 7. Add to Registry Run key (Failsafe 3)
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RemoteDeskAgent" /t REG_SZ /d "wscript.exe \"%VBS_SCRIPT%\"" /f >nul
echo [OK] Registered Windows Run registry key.

echo.
echo ==============================================================
echo  SUCCESS! RemoteDesk Agent is now configured to start
echo  automatically whenever Windows boots up or logs in.
echo ==============================================================
echo.
echo Starting agent in background now...
wscript.exe "%VBS_SCRIPT%"

echo Check "%AGENT_DIR%agent.log" to view live connection logs.
echo.
pause
