@echo off
:: ==============================================================
:: RemoteDesk - Build Standalone Windows .exe
:: Compiles agent.py into a single, zero-dependency executable.
:: ==============================================================

echo Installing build dependencies...
python -m pip install pyinstaller mss pillow pyautogui websockets

echo Building RemoteDeskAgent.exe...
pyinstaller --noconsole --onefile --name "RemoteDeskAgent" agent.py

echo.
echo Build Complete!
echo The standalone executable is located in: dist\RemoteDeskAgent.exe
pause

