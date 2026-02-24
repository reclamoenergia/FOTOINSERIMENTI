#!/usr/bin/env bash
set -euo pipefail

BASE_REF="eebc76f"
TARGET_BRANCH="${1:-auto/batch-shapefile}"
SOURCE_REF="${2:-HEAD}"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERRORE: working tree non pulito. Fai commit/stash prima di procedere." >&2
  exit 1
fi

git rev-parse --verify "$BASE_REF" >/dev/null
git rev-parse --verify "$SOURCE_REF" >/dev/null

echo "[1/3] Checkout branch $TARGET_BRANCH da $BASE_REF"
git checkout -B "$TARGET_BRANCH" "$BASE_REF"

echo "[2/3] Merge fast-forward da $SOURCE_REF (senza conflitti)"
git merge --ff-only "$SOURCE_REF"

echo "[3/3] Fatto. Branch pronto: $TARGET_BRANCH"
echo "Push suggerito: git push -u origin $TARGET_BRANCH"
