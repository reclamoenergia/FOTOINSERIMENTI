from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

from .horizon import TurbineAngleResult


def _format_log_lines(markers: Iterable[TurbineAngleResult]) -> list[str]:
    lines = []
    for m in markers:
        vis = "YES" if m.visible_hub else "NO"
        lines.append(
            f"{m.turbine_id}: az={m.azimuth_deg:.2f}°, hub={m.e_hub_deg:.2f}°, hor={m.e_horizon_deg:.2f}°, vis={vis}"
        )
    return lines


def render_horizon_png(
    az_plot: np.ndarray,
    elev_horizon: np.ndarray,
    turbine_markers: list[TurbineAngleResult],
    view_marker: Optional[Tuple[float, str]],
    output_path: str | Path,
    transparent: bool = False,
) -> None:
    fig, ax = plt.subplots(figsize=(13, 7), dpi=120)

    ax.plot(az_plot, elev_horizon, color="tab:blue", linewidth=2.0, label="Horizon")

    for marker in turbine_markers:
        x = marker.azimuth_plot_deg
        ax.axvline(x=x, color="tab:gray", linestyle="--", linewidth=0.8, alpha=0.7)
        ax.plot([x, x], [marker.e_base_deg, marker.e_hub_deg], color="tab:green", linewidth=2.2)
        ax.scatter([x], [marker.e_horizon_deg], color="tab:red", s=16, zorder=4)

        if marker.e_tip_deg is not None:
            ax.scatter([x], [marker.e_tip_deg], color="tab:purple", s=14, zorder=4)

        ax.text(x + 0.05, marker.e_hub_deg + 0.12, marker.turbine_id, fontsize=8, color="black")

    if view_marker is not None:
        view_az, label = view_marker
        ax.axvline(x=view_az, color="black", linestyle="-", linewidth=1.8, label=label)
        ymax = float(np.nanmax(elev_horizon)) if len(elev_horizon) > 0 else 0.0
        ax.text(view_az + 0.05, ymax + 0.4, label, fontsize=9, weight="bold")

    ax.set_title("Horizon profile")
    ax.set_xlabel("Azimut (deg)")
    ax.set_ylabel("Elevazione (deg)")
    ax.grid(True, linestyle=":", alpha=0.5)

    y_min_candidates = [float(np.nanmin(elev_horizon))] if len(elev_horizon) else []
    y_min_candidates.extend(m.e_base_deg for m in turbine_markers)
    y_min = min(y_min_candidates, default=-5.0)
    y_max_candidates = [float(np.nanmax(elev_horizon))] if len(elev_horizon) else [10.0]
    y_max_candidates.extend(m.e_hub_deg for m in turbine_markers)
    y_max_candidates.extend(m.e_tip_deg for m in turbine_markers if m.e_tip_deg is not None)
    y_max = max(y_max_candidates) if y_max_candidates else 10.0

    margin = 1.0
    ax.set_ylim(y_min - margin, y_max + margin)

    lines = _format_log_lines(turbine_markers)
    if lines:
        preview = "\n".join(lines[:10])
        ax.text(
            1.005,
            0.98,
            preview,
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=8,
            family="monospace",
            bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "lightgray"},
        )

    ax.legend(loc="upper left")
    plt.tight_layout()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, transparent=transparent)
    plt.close(fig)
