from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from .dtm import DTM


@dataclass
class HorizonSample:
    azimuth_plot_deg: float
    azimuth_deg: float
    elevation_deg: float
    distance_m: float


@dataclass
class TurbineAngleResult:
    turbine_id: str
    azimuth_deg: float
    azimuth_plot_deg: float
    distance_m: float
    e_base_deg: float
    e_hub_deg: float
    e_tip_deg: float | None
    e_horizon_deg: float
    visible_hub: bool


def azimuth_deg(x0: float, y0: float, xt: float, yt: float) -> float:
    dx = xt - x0
    dy = yt - y0
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def elevation_deg(z0: float, z: float, d_horizontal: float) -> float:
    return math.degrees(math.atan2(z - z0, d_horizontal))


def build_azimuth_axis(az_start: float, az_end: float, az_step: float) -> np.ndarray:
    if az_step <= 0:
        raise ValueError("az_step must be > 0")
    if az_start <= az_end:
        return np.arange(az_start, az_end + az_step * 0.5, az_step, dtype=float)
    return np.arange(az_start, az_end + 360.0 + az_step * 0.5, az_step, dtype=float)


def compute_horizon_profile(
    dtm_path: str | Path,
    observer_xy: tuple[float, float],
    observer_z: float,
    az_start: float,
    az_end: float,
    az_step: float,
    max_range: float,
    step_m: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, int]]:
    if max_range <= 0:
        raise ValueError("max_range must be > 0")

    x0, y0 = observer_xy
    az_plot = build_azimuth_axis(az_start, az_end, az_step)
    elev = np.full(az_plot.shape, -90.0, dtype=float)
    dist = np.zeros_like(elev)

    nodata_count = 0
    with DTM(dtm_path) as dtm:
        sample_step = step_m if step_m > 0 else dtm.pixel_size
        if sample_step <= 0:
            raise ValueError("Sampling step must be > 0")
        distances = np.arange(sample_step, max_range + sample_step * 0.5, sample_step, dtype=float)

        for i, azp in enumerate(az_plot):
            az = azp % 360.0
            a = math.radians(az)
            sin_a = math.sin(a)
            cos_a = math.cos(a)
            best_e = -90.0
            best_d = 0.0
            for d in distances:
                x = x0 + d * sin_a
                y = y0 + d * cos_a
                s = dtm.sample_nearest(x, y)
                if s.is_nodata or s.value is None:
                    nodata_count += 1
                    continue
                e = elevation_deg(observer_z, s.value, d)
                if e > best_e:
                    best_e = e
                    best_d = float(d)
            elev[i] = best_e
            dist[i] = best_d

    return az_plot, elev, dist, {"nodata_samples": nodata_count}


def interpolate_horizon_elevation(az_plot: np.ndarray, elev: np.ndarray, azimuth_deg_value: float) -> float:
    if len(az_plot) == 0:
        return float("nan")
    az_mod = azimuth_deg_value % 360.0
    axis_mod = np.mod(az_plot, 360.0)
    order = np.argsort(axis_mod)
    xs = axis_mod[order]
    ys = elev[order]
    xs_ext = np.concatenate([xs, xs[:1] + 360.0])
    ys_ext = np.concatenate([ys, ys[:1]])
    return float(np.interp(az_mod, xs_ext, ys_ext))


def turbine_angles(
    observer_xyz: tuple[float, float, float],
    turbines: list[dict[str, Any]],
    az_plot: np.ndarray,
    elev_horizon: np.ndarray,
) -> list[TurbineAngleResult]:
    x0, y0, z0 = observer_xyz
    out: list[TurbineAngleResult] = []
    for t in turbines:
        tid = str(t.get("id", "WTG"))
        bx, by, bz = [float(v) for v in t["base_xyz"]]
        th = float(t["tower_height_m"])
        rd = float(t.get("rotor_diameter_m", 0.0))
        d = math.hypot(bx - x0, by - y0)
        if d <= 1e-6:
            d = 1e-6
        az = azimuth_deg(x0, y0, bx, by)
        e_base = elevation_deg(z0, bz, d)
        e_hub = elevation_deg(z0, bz + th, d)
        e_tip = elevation_deg(z0, bz + th + rd * 0.5, d) if rd > 0 else None
        e_hor = interpolate_horizon_elevation(az_plot, elev_horizon, az)
        out.append(
            TurbineAngleResult(
                turbine_id=tid,
                azimuth_deg=az,
                azimuth_plot_deg=az,
                distance_m=d,
                e_base_deg=e_base,
                e_hub_deg=e_hub,
                e_tip_deg=e_tip,
                e_horizon_deg=e_hor,
                visible_hub=e_hub > e_hor,
            )
        )
    return out


def _centroid_hubs(turbines: list[dict[str, Any]]) -> tuple[float, float, float]:
    hubs = []
    for t in turbines:
        bx, by, bz = [float(v) for v in t["base_xyz"]]
        hubs.append((bx, by, bz + float(t["tower_height_m"])))
    if not hubs:
        raise ValueError("No turbines provided")
    arr = np.array(hubs, dtype=float)
    c = arr.mean(axis=0)
    return float(c[0]), float(c[1]), float(c[2])


def build_from_config(config: dict[str, Any]) -> dict[str, Any]:
    dtm_path = config["dtm"]["geotiff_path"]
    ox, oy, oz = [float(v) for v in config["observer"]["position_xyz"]]
    eye_h = float(config["observer"].get("eye_height_m", 0.0))
    obs_z = oz + eye_h

    az_start = float(config["azimuth"]["start_deg"])
    az_end = float(config["azimuth"]["end_deg"])
    az_step = float(config["azimuth"]["step_deg"])
    max_range = float(config["range"]["max_m"])
    step_m = float(config["range"].get("step_m", 0.0))

    turbines = config.get("turbines", [])
    az_plot, elev_horizon, _, stats = compute_horizon_profile(
        dtm_path=dtm_path,
        observer_xy=(ox, oy),
        observer_z=obs_z,
        az_start=az_start,
        az_end=az_end,
        az_step=az_step,
        max_range=max_range,
        step_m=step_m,
    )

    markers = turbine_angles((ox, oy, obs_z), turbines, az_plot, elev_horizon)
    target = _centroid_hubs(turbines) if turbines else (ox, oy + 1.0, obs_z)
    view_az = azimuth_deg(ox, oy, target[0], target[1])

    return {
        "az_plot": az_plot,
        "elev_horizon": elev_horizon,
        "turbine_markers": markers,
        "view_marker": (view_az, "View"),
        "observer_xyz": (ox, oy, obs_z),
        "stats": stats,
    }


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)
