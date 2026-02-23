# Patch completa (reset da base)

Questa patch contiene **tutte** le modifiche batch-shapefile a partire da commit base:

- Base: `eebc76f`
- Output patch: `PATCH_BATCH_SHAPEFILE_FULL.diff`

## Come applicarla da zero

```bash
git checkout -b fix-batch-shapefile eebc76f
git apply --index PATCH_BATCH_SHAPEFILE_FULL.diff
git commit -m "Add batch shapefile mode with text-only sample assets"
```

## Verifica

```bash
python -m compileall src examples/create_observer_shapefile.py
python -m json.tool examples/observer_points.geojson
```
