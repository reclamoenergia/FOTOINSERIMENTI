from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from .camera_model import hfov_vfov_deg
from .horizon import azimuth_deg, elevation_deg


def render_horizon_profile_png(
    output_path: str | Path,
    az_plot: np.ndarray,
    elev_horizon: np.ndarray,
    observer_xyz: tuple[float, float, float],
    turbines: list[dict[str, Any]],
    focal_mm: float,
    sensor_w_mm: float,
    sensor_h_mm: float,
    view_az_deg: float,
    view_elev_deg: float,
    transparent: bool = False,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 7), dpi=120)
    ax.plot(az_plot, elev_horizon, color="tab:blue", linewidth=2, label="Horizon")

    ox, oy, oz = observer_xyz
    for t in turbines:
        bx, by, bz = [float(v) for v in t["base_xyz"]]
        th = float(t["tower_height_m"])
        d = max(np.hypot(bx - ox, by - oy), 1e-6)
        az = azimuth_deg(ox, oy, bx, by)
        e_base = elevation_deg(oz, bz, d)
        e_hub = elevation_deg(oz, bz + th, d)
        ax.plot([az, az], [e_base, e_hub], color="tab:green", linewidth=2)
        ax.text(az + 0.05, e_hub + 0.1, str(t.get("id", "WTG")), fontsize=8)

    hfov, vfov = hfov_vfov_deg(focal_mm, sensor_w_mm, sensor_h_mm)
    ax.axvspan(view_az_deg - hfov / 2.0, view_az_deg + hfov / 2.0, color="orange", alpha=0.15, label="HFOV")
    ax.axhline(view_elev_deg - vfov / 2.0, color="orange", linestyle="--", linewidth=1.3)
    ax.axhline(view_elev_deg + vfov / 2.0, color="orange", linestyle="--", linewidth=1.3)
    ax.axvline(view_az_deg, color="black", linewidth=1.2, label="View")

    ax.set_xlabel("Azimuth (deg)")
    ax.set_ylabel("Elevation (deg)")
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(loc="best")

    if len(az_plot):
        ax.set_xlim(float(np.nanmin(az_plot)), float(np.nanmax(az_plot)))
    fig.tight_layout()
    fig.savefig(output_path, transparent=transparent)
    plt.close(fig)
