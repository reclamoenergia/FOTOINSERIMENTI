@echo off
setlocal

REM Build standalone Windows executable (GUI only, no console)
python -m PyInstaller --noconsole --onefile --name WTGUnifiedView src\gui_unified.py

echo Build completed. Executable is in dist\WTGUnifiedView.exe
endlocal
