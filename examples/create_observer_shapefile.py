from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    """Create observer_points shapefile from the text GeoJSON sample.

    Requires fiona (already declared in requirements.txt).
    """

    try:
        import fiona
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing dependency 'fiona'. Run: pip install -r requirements.txt") from exc

    base_dir = Path(__file__).resolve().parent
    src_geojson = base_dir / "observer_points.geojson"
    out_shp = base_dir / "observer_points.shp"

    data = json.loads(src_geojson.read_text(encoding="utf-8"))
    features = data.get("features", [])
    crs_name = ((data.get("crs") or {}).get("properties") or {}).get("name", "EPSG:32632")

    schema = {"geometry": "Point", "properties": {"Nome": "str:80"}}

    # Remove previous dataset if present
    for ext in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
        p = out_shp.with_suffix(ext)
        if p.exists():
            p.unlink()

    with fiona.open(out_shp, mode="w", driver="ESRI Shapefile", schema=schema, crs=crs_name, encoding="UTF-8") as dst:
        for feat in features:
            geom = feat.get("geometry") or {}
            props = feat.get("properties") or {}
            dst.write({
                "geometry": geom,
                "properties": {"Nome": str(props.get("Nome", ""))},
            })

    print(f"Created: {out_shp}")


if __name__ == "__main__":
    main()
