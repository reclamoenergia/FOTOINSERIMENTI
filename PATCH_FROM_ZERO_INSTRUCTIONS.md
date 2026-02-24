# Patch da zero (senza conflitti)

Questa patch applica **tutte** le modifiche dal commit base `eebc76f` fino a `HEAD` (86bbca7).

## 1) Applica in un branch nuovo dalla base

```bash
git checkout -b apply-batch-from-zero eebc76f
git apply --index PATCH_FROM_ZERO_BATCH_SHAPEFILE.diff
git commit -m "Apply full batch-shapefile patch from zero"
```

## 2) Verifica veloce

```bash
python -m compileall src examples/create_observer_shapefile.py
python -m json.tool examples/observer_points.geojson
```
