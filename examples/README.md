# Esempio osservatori batch (senza binari nel repo)

Per evitare errori PR su file binari, nel repository sono inclusi solo file **testuali**.

Contenuto:
- `observer_points.geojson` (3 punti, campo attributo `Nome`, CRS `EPSG:32632`)
- `create_observer_shapefile.py` per generare localmente lo shapefile `observer_points.*`

Generazione shapefile locale:
```bash
python examples/create_observer_shapefile.py
```

File prodotti in locale (non versionati nel repo):
- `observer_points.shp`
- `observer_points.shx`
- `observer_points.dbf`
- `observer_points.prj`
- `observer_points.cpg`
