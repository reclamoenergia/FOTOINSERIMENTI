from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    """Create observer_points shapefile from the text GeoJSON sample.

    Requires pyshp (shapefile package) declared in requirements.txt.
    """

    try:
        import shapefile
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing dependency 'pyshp'. Run: pip install -r requirements.txt") from exc

    base_dir = Path(__file__).resolve().parent
    src_geojson = base_dir / "observer_points.geojson"
    out_shp = base_dir / "observer_points.shp"

    data = json.loads(src_geojson.read_text(encoding="utf-8"))
    features = data.get("features", [])
    crs_name = ((data.get("crs") or {}).get("properties") or {}).get("name", "EPSG:32632")

    for ext in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
        p = out_shp.with_suffix(ext)
        if p.exists():
            p.unlink()

    writer = shapefile.Writer(str(out_shp), shapeType=shapefile.POINT)
    writer.field("Nome", "C", size=80)

    for feat in features:
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        x, y = float(coords[0]), float(coords[1])
        nome = str((feat.get("properties") or {}).get("Nome", ""))
        writer.point(x, y)
        writer.record(nome)

    writer.close()

    prj_wkt = (
        'PROJCS["WGS_1984_UTM_Zone_32N",GEOGCS["GCS_WGS_1984",'
        'DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
        'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
        'PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",500000.0],'
        'PARAMETER["False_Northing",0.0],PARAMETER["Central_Meridian",9.0],'
        'PARAMETER["Scale_Factor",0.9996],PARAMETER["Latitude_Of_Origin",0.0],'
        'UNIT["Meter",1.0]]'
    )
    if crs_name.upper() == "EPSG:32632":
        out_shp.with_suffix('.prj').write_text(prj_wkt, encoding='utf-8')
    else:
        out_shp.with_suffix('.prj').write_text(prj_wkt, encoding='utf-8')
    out_shp.with_suffix('.cpg').write_text('UTF-8', encoding='utf-8')

    print(f"Created: {out_shp}")


if __name__ == "__main__":
    main()
