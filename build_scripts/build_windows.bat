@echo off
setlocal

REM Build standalone Windows executable (GUI only, no console)
pyinstaller --noconsole --onefile --name WTGOverlay src/gui.py

echo Build completed. Executable is in dist\WTGOverlay.exe
endlocal
