from __future__ import annotations

import json
from pathlib import Path

import shapefile


def main() -> None:
    """Create observer_points shapefile from the text GeoJSON sample."""

    base_dir = Path(__file__).resolve().parent
    src_geojson = base_dir / "observer_points.geojson"
    out_shp = base_dir / "observer_points.shp"

    data = json.loads(src_geojson.read_text(encoding="utf-8"))
    features = data.get("features", [])
    crs_name = ((data.get("crs") or {}).get("properties") or {}).get("name", "EPSG:32632")

    # Remove previous dataset if present
    for ext in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
        p = out_shp.with_suffix(ext)
        if p.exists():
            p.unlink()

    with shapefile.Writer(str(out_shp), shapeType=shapefile.POINT, encoding="utf-8") as dst:
        dst.field("Nome", "C", size=80)
        for feat in features:
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") or []
            if geom.get("type") != "Point" or len(coords) < 2:
                continue
            dst.point(float(coords[0]), float(coords[1]))
            props = feat.get("properties") or {}
            dst.record(str(props.get("Nome", "")))

    out_shp.with_suffix('.prj').write_text(
        (
            'PROJCS["WGS 84 / UTM zone 32N",GEOGCS["WGS 84",DATUM["WGS_1984",'
            'SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],'
            'UNIT["degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
            'PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",9],'
            'PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],'
            'PARAMETER["false_northing",0],UNIT["metre",1],AXIS["Easting",EAST],'
            'AXIS["Northing",NORTH],AUTHORITY["EPSG","32632"]]'
            if crs_name.upper() == "EPSG:32632"
            else crs_name
        ),
        encoding='utf-8',
    )
    out_shp.with_suffix('.cpg').write_text('UTF-8', encoding='utf-8')

    print(f"Created: {out_shp}")


if __name__ == "__main__":
    main()
