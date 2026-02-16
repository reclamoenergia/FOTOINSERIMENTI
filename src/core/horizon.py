from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .dtm_sampler import DTMSampler

Vector3 = Tuple[float, float, float]


@dataclass
class TurbineAngleResult:
    turbine_id: str
    azimuth_deg: float
    azimuth_plot_deg: float
    distance_m: float
    e_base_deg: float
    e_hub_deg: float
    e_tip_deg: Optional[float]
    e_horizon_deg: float
    visible_hub: bool


def azimuth_deg(x0: float, y0: float, xt: float, yt: float) -> float:
    dx = xt - x0
    dy = yt - y0
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def elevation_deg(z0: float, z: float, d_horizontal: float) -> float:
    return math.degrees(math.atan2(z - z0, d_horizontal))


def _build_azimuth_axis(az_start: float, az_end: float, az_step: float) -> np.ndarray:
    if az_step <= 0:
        raise ValueError("az_step must be > 0")
    if az_start <= az_end:
        return np.arange(az_start, az_end + az_step * 0.5, az_step, dtype=float)
    return np.arange(az_start, az_end + 360.0 + az_step * 0.5, az_step, dtype=float)


def _as_turbine_dict(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    tid = str(item.get("id", f"WTG{index + 1:02d}"))
    base_xyz = item.get("base_xyz")
    if not isinstance(base_xyz, list) or len(base_xyz) != 3:
        raise ValueError(f"Turbine {tid}: base_xyz must contain 3 numbers")
    return {
        "id": tid,
        "base_xyz": (float(base_xyz[0]), float(base_xyz[1]), float(base_xyz[2])),
        "tower_height_m": float(item.get("tower_height_m", 0.0)),
        "rotor_diameter_m": float(item.get("rotor_diameter_m", 0.0)),
    }


def compute_horizon_profile(
    dtm_path: str | Path,
    observer_xyz: Vector3,
    az_start: float,
    az_end: float,
    az_step: float,
    max_range: float,
    step_m: float,
    eye_height: float,
    use_bilinear: bool = True,
    max_consecutive_nodata: int = 25,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute skyline profile as max elevation angle along each azimuth ray."""
    if max_range <= 0:
        raise ValueError("max_range must be > 0")

    x0, y0, z0 = observer_xyz
    z_obs = z0 + eye_height
    az_plot = _build_azimuth_axis(az_start, az_end, az_step)

    with DTMSampler(dtm_path) as sampler:
        sample_step = step_m if step_m > 0 else sampler.pixel_size
        if sample_step <= 0:
            raise ValueError("Invalid sampling step from DTM")

        distances = np.arange(sample_step, max_range + sample_step * 0.5, sample_step, dtype=float)
        horizon = np.full_like(az_plot, fill_value=np.nan, dtype=float)

        for i, azp in enumerate(az_plot):
            az = azp % 360.0
            az_rad = math.radians(az)
            sin_a = math.sin(az_rad)
            cos_a = math.cos(az_rad)

            best_elev = -90.0
            nodata_streak = 0

            for d in distances:
                x = x0 + d * sin_a
                y = y0 + d * cos_a

                if use_bilinear:
                    sample = sampler.sample_bilinear(x, y)
                else:
                    sample = sampler.sample_nearest(x, y)

                if sample.is_nodata or sample.value is None:
                    nodata_streak += 1
                    if nodata_streak >= max_consecutive_nodata:
                        break
                    continue

                nodata_streak = 0
                e = elevation_deg(z_obs, sample.value, d)
                if e > best_elev:
                    best_elev = e

            horizon[i] = best_elev

    return az_plot, horizon


def compute_turbine_angles(observer_xyz: Vector3, turbine: Dict[str, Any]) -> Tuple[float, float, float, Optional[float]]:
    x0, y0, z0 = observer_xyz
    base_x, base_y, base_z = turbine["base_xyz"]
    tower_h = float(turbine["tower_height_m"])
    rotor_d = float(turbine.get("rotor_diameter_m", 0.0))

    az = azimuth_deg(x0, y0, base_x, base_y)
    d = math.hypot(base_x - x0, base_y - y0)
    e_base = elevation_deg(z0, base_z, d)
    e_hub = elevation_deg(z0, base_z + tower_h, d)
    e_tip = elevation_deg(z0, base_z + tower_h + rotor_d / 2.0, d) if rotor_d > 0 else None
    return az, e_base, e_hub, e_tip


def build_turbine_markers(
    observer_xyz: Vector3,
    eye_height_m: float,
    turbines_data: List[Dict[str, Any]],
    az_plot: np.ndarray,
    elev_horizon: np.ndarray,
    az_start: float,
    wrapped_axis: bool,
) -> List[TurbineAngleResult]:
    x0, y0, z0 = observer_xyz
    z_obs = z0 + eye_height_m
    markers: List[TurbineAngleResult] = []

    valid_horizon = np.nan_to_num(elev_horizon, nan=-90.0)

    for i, t_raw in enumerate(turbines_data):
        t = _as_turbine_dict(t_raw, i)
        tx, ty, tz = t["base_xyz"]
        az = azimuth_deg(x0, y0, tx, ty)
        az_plot_value = az + 360.0 if wrapped_axis and az < az_start else az

        d = math.hypot(tx - x0, ty - y0)
        if d <= 0:
            continue

        e_base = elevation_deg(z_obs, tz, d)
        hub_z = tz + t["tower_height_m"]
        e_hub = elevation_deg(z_obs, hub_z, d)
        if t["rotor_diameter_m"] > 0:
            e_tip = elevation_deg(z_obs, hub_z + t["rotor_diameter_m"] / 2.0, d)
        else:
            e_tip = None

        e_hor = float(np.interp(az_plot_value, az_plot, valid_horizon))
        markers.append(
            TurbineAngleResult(
                turbine_id=t["id"],
                azimuth_deg=az,
                azimuth_plot_deg=az_plot_value,
                distance_m=d,
                e_base_deg=e_base,
                e_hub_deg=e_hub,
                e_tip_deg=e_tip,
                e_horizon_deg=e_hor,
                visible_hub=e_hub > e_hor,
            )
        )

    return markers


def compute_view_marker(
    observer_xyz: Vector3,
    turbines_data: List[Dict[str, Any]],
    az_start: float,
    wrapped_axis: bool,
    view_direction: Dict[str, Any],
) -> Optional[Tuple[float, str]]:
    mode = (view_direction or {}).get("mode", "centroid")
    if not turbines_data:
        return None

    x0, y0, _ = observer_xyz
    turbines = [_as_turbine_dict(t, i) for i, t in enumerate(turbines_data)]

    if mode == "turbine_id":
        target_id = view_direction.get("turbine_id")
        target = next((t for t in turbines if t["id"] == target_id), None)
        if target is None:
            return None
        tx, ty, _ = target["base_xyz"]
        az = azimuth_deg(x0, y0, tx, ty)
        label = f"VIEW {target_id}"
    else:
        hubs = [
            (
                t["base_xyz"][0],
                t["base_xyz"][1],
                t["base_xyz"][2] + t["tower_height_m"],
            )
            for t in turbines
        ]
        cx = sum(p[0] for p in hubs) / len(hubs)
        cy = sum(p[1] for p in hubs) / len(hubs)
        az = azimuth_deg(x0, y0, cx, cy)
        label = "VIEW"

    az_plot_value = az + 360.0 if wrapped_axis and az < az_start else az
    return az_plot_value, label


def build_from_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    dtm_path = cfg["dtm"]["geotiff_path"]
    observer_xyz = tuple(float(v) for v in cfg["observer"]["position_xyz"])
    eye_h = float(cfg["observer"].get("eye_height_m", 1.6))

    az_start = float(cfg["azimuth"]["start_deg"])
    az_end = float(cfg["azimuth"]["end_deg"])
    az_step = float(cfg["azimuth"].get("step_deg", 0.2))

    max_range = float(cfg["range"].get("max_m", 30000.0))
    step_m = float(cfg["range"].get("step_m", 0.0))

    az_plot, elev_horizon = compute_horizon_profile(
        dtm_path=dtm_path,
        observer_xyz=observer_xyz,
        az_start=az_start,
        az_end=az_end,
        az_step=az_step,
        max_range=max_range,
        step_m=step_m,
        eye_height=eye_h,
    )

    wrapped_axis = az_start > az_end
    turbines = cfg.get("turbines", [])
    markers = build_turbine_markers(
        observer_xyz=observer_xyz,
        eye_height_m=eye_h,
        turbines_data=turbines,
        az_plot=az_plot,
        elev_horizon=elev_horizon,
        az_start=az_start,
        wrapped_axis=wrapped_axis,
    )
    view_marker = compute_view_marker(
        observer_xyz=observer_xyz,
        turbines_data=turbines,
        az_start=az_start,
        wrapped_axis=wrapped_axis,
        view_direction=cfg.get("view_direction", {"mode": "centroid"}),
    )

    return {
        "config": cfg,
        "az_plot": az_plot,
        "elev_horizon": elev_horizon,
        "turbine_markers": markers,
        "view_marker": view_marker,
    }


def build_from_json_config(config_path: str | Path) -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as fp:
        cfg = json.load(fp)
    return build_from_config(cfg)
