@echo off
setlocal

REM Build standalone Windows executable (GUI only, no console)
REM We include extra PyInstaller flags for rasterio to avoid runtime errors like:
REM ModuleNotFoundError: No module named 'rasterio.sample'

set BASE_CMD=pyinstaller --noconsole --onefile --name WTGOverlay src/gui.py
set RASTERIO_FLAGS=

python -c "import rasterio" >nul 2>nul
if %errorlevel%==0 (
  echo Rasterio detected: enabling hidden-import/collect-submodules flags.
  set RASTERIO_FLAGS=--hidden-import rasterio.sample --collect-submodules rasterio --collect-data rasterio
) else (
  echo Rasterio not detected in this environment: building without rasterio-specific flags.
)

%BASE_CMD% %RASTERIO_FLAGS%
if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

echo Build completed. Executable is in dist\WTGOverlay.exe
endlocal
