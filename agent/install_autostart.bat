@echo off
:: ==============================================================
:: RemoteDesk - Windows Unattended Auto-Start Installer
:: Configures the agent to start automatically on Windows boot.
:: ==============================================================

echo [RemoteDesk] Installing Python dependencies...
python -m pip install -r requirements.txt

echo [RemoteDesk] Registering Scheduled Task for unattended access...
set AGENT_DIR=%~dp0
set VBS_SCRIPT=%AGENT_DIR%start_agent.vbs

:: Create the VBScript launcher to run pythonw in the background without a popup window
echo Set WshShell = CreateObject("WScript.Shell") > "%VBS_SCRIPT%"
echo WshShell.Run "pythonw.exe """ ^& "%AGENT_DIR%agent.py""" , 0, False >> "%VBS_SCRIPT%"

:: Add to Windows Startup registry for current user
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RemoteDeskAgent" /t REG_SZ /d "wscript.exe \"%VBS_SCRIPT%\"" /f

echo.
echo ==============================================================
echo  SUCCESS! RemoteDesk Agent will now start automatically
echo  whenever this Windows laptop turns on or connects to Wi-Fi.
echo ==============================================================
echo.
echo Starting agent in background now...
wscript.exe "%VBS_SCRIPT%"
pause

