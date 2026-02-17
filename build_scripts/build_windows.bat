@echo off
setlocal EnableExtensions

REM =========================================================
REM Build Windows EXE (WTGOverlay) - no console
REM Robust version: checks tools, paths, and returns proper code
REM =========================================================

REM Move to repository root (script is in build_scripts\)
pushd "%~dp0\.." || (
  echo [ERROR] Cannot move to repository root.
  exit /b 1
)

set "APP_ENTRY=src\gui.py"
set "HOOK_DIR=build_scripts\hooks"
set "APP_NAME=WTGOverlay"

if not exist "%APP_ENTRY%" (
  echo [ERROR] Entry file not found: %APP_ENTRY%
  popd
  exit /b 1
)

if not exist "%HOOK_DIR%" (
  echo [ERROR] Hook directory not found: %HOOK_DIR%
  popd
  exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found in PATH.
  popd
  exit /b 1
)

echo [INFO] Cleaning previous build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [INFO] Running PyInstaller...
python -m PyInstaller ^
  --noconsole ^
  --onefile ^
  --name "%APP_NAME%" ^
  "%APP_ENTRY%" ^
  --additional-hooks-dir "%HOOK_DIR%" ^
  --hidden-import rasterio.sample ^
  --collect-submodules rasterio ^
  --collect-data rasterio

if errorlevel 1 (
  echo [ERROR] Build failed.
  echo [HINT] Use the same virtualenv where rasterio is installed.
  popd
  exit /b 1
)

if exist "dist\%APP_NAME%.exe" (
  echo [OK] Build completed: dist\%APP_NAME%.exe
  popd
  exit /b 0
) else (
  echo [ERROR] Build command finished but EXE not found.
  popd
  exit /b 1
)
