@echo off
setlocal

set BASE_REF=eebc76f
set TARGET_BRANCH=auto/batch-shapefile
set SOURCE_REF=HEAD

if not "%~1"=="" set TARGET_BRANCH=%~1
if not "%~2"=="" set SOURCE_REF=%~2

for /f %%i in ('git status --porcelain') do set DIRTY=1
if defined DIRTY (
  echo ERRORE: working tree non pulito. Fai commit/stash prima di procedere.
  exit /b 1
)

git rev-parse --verify %BASE_REF% >nul 2>&1
if errorlevel 1 (
  echo ERRORE: base commit %BASE_REF% non trovato.
  exit /b 1
)

git rev-parse --verify %SOURCE_REF% >nul 2>&1
if errorlevel 1 (
  echo ERRORE: source ref %SOURCE_REF% non trovato.
  exit /b 1
)

echo [1/3] Checkout branch %TARGET_BRANCH% da %BASE_REF%
git checkout -B %TARGET_BRANCH% %BASE_REF% || exit /b 1

echo [2/3] Merge fast-forward da %SOURCE_REF% (senza conflitti)
git merge --ff-only %SOURCE_REF% || exit /b 1

echo [3/3] Fatto. Branch pronto: %TARGET_BRANCH%
echo Push suggerito: git push -u origin %TARGET_BRANCH%

endlocal
