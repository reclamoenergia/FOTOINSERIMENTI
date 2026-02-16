@echo off
setlocal

REM Build standalone Windows executable (GUI only, no console)
REM Uses a custom PyInstaller hook to bundle rasterio submodules/dll/data.

set PYI_FLAGS=--noconsole --onefile --name WTGOverlay src/gui.py --additional-hooks-dir build_scripts/hooks --hidden-import rasterio.sample --collect-submodules rasterio --collect-data rasterio

echo Running: pyinstaller %PYI_FLAGS%
pyinstaller %PYI_FLAGS%
if errorlevel 1 (
  echo Build failed.
  echo If rasterio is used by your app, ensure you build inside the same venv where rasterio is installed.
  exit /b 1
)

echo Build completed. Executable is in dist\WTGOverlay.exe
endlocal
