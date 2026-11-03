@echo off
echo Stopping RemoteDesk background processes...
taskkill /f /im pythonw.exe
echo Done.
pause

