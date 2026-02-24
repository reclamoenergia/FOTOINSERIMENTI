@echo off
setlocal EnableExtensions

REM =========================================================
REM Build Windows EXE (WTGUnifiedView) - no console
REM Includes rasterio dependencies used by batch shapefile mode
REM =========================================================

REM Move to repository root (script is in build_scripts\)
pushd "%~dp0\.."
if errorlevel 1 goto :err_repo

set "APP_ENTRY=src\gui_unified.py"
set "HOOK_DIR=build_scripts\hooks"
set "APP_NAME=WTGUnifiedView"
set "DIST_EXE=dist\%APP_NAME%.exe"

if not exist "%APP_ENTRY%" goto :err_entry
if not exist "%HOOK_DIR%" goto :err_hooks

where python >nul 2>nul
if errorlevel 1 goto :err_python

echo [INFO] Cleaning previous build artifacts...
if exist build rmdir /s /q build

if exist "%DIST_EXE%" (
  echo [INFO] Removing previous executable: %DIST_EXE%
  del /f /q "%DIST_EXE%" >nul 2>nul
)

if exist "%DIST_EXE%" (
  echo [WARN] Previous EXE is locked. Trying to stop running process %APP_NAME%.exe ...
  taskkill /f /im "%APP_NAME%.exe" >nul 2>nul
  timeout /t 1 /nobreak >nul
  del /f /q "%DIST_EXE%" >nul 2>nul
)

if exist "%DIST_EXE%" goto :err_locked
if exist dist rmdir /s /q dist

echo [INFO] Running PyInstaller...
python -m PyInstaller ^
  --noconfirm ^
  --noconsole ^
  --onefile ^
  --name "%APP_NAME%" ^
  "%APP_ENTRY%" ^
  --additional-hooks-dir "%HOOK_DIR%" ^
  --hidden-import rasterio.sample ^
  --hidden-import shapefile ^
  --collect-submodules rasterio ^
  --collect-data rasterio
if errorlevel 1 goto :err_build

if exist "%DIST_EXE%" goto :ok

echo [ERROR] Build command finished but EXE not found.
popd
exit /b 1

:ok
echo [OK] Build completed: %DIST_EXE%
popd
exit /b 0

:err_repo
echo [ERROR] Cannot move to repository root.
exit /b 1

:err_entry
echo [ERROR] Entry file not found: %APP_ENTRY%
popd
exit /b 1

:err_hooks
echo [ERROR] Hook directory not found: %HOOK_DIR%
popd
exit /b 1

:err_python
echo [ERROR] Python not found in PATH.
popd
exit /b 1

:err_locked
echo [ERROR] Cannot overwrite %DIST_EXE% (file is still in use).
echo [HINT] Close the running EXE and retry the build.
popd
exit /b 1

:err_build
echo [ERROR] Build failed.
echo [HINT] Use the same virtualenv where rasterio is installed.
popd
exit /b 1
