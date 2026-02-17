from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .camera_model import CameraIntrinsics, CameraPose, project_point


@dataclass
class CameraRenderResult:
    inside_ids: list[str]
    outside_ids: list[str]


def _wrap_pi(rad: float) -> float:
    return (rad + math.pi) % (2.0 * math.pi) - math.pi


def render_camera_view_png(
    output_path: str | Path,
    intr: CameraIntrinsics,
    pose: CameraPose,
    az_plot: np.ndarray,
    elev_horizon_deg: np.ndarray,
    view_az_deg: float,
    view_elev_deg: float,
    turbines: list[dict[str, Any]],
    transparent: bool = False,
    draw_crosshair: bool = True,
) -> CameraRenderResult:
    mode = "RGBA"
    bg = (0, 0, 0, 0) if transparent else (0, 0, 0, 255)
    im = Image.new(mode, (intr.width_px, intr.height_px), bg)
    draw = ImageDraw.Draw(im)
    try:
        label_font = ImageFont.truetype("DejaVuSans.ttf", 20)
    except OSError:
        label_font = ImageFont.load_default()

    # Skyline projected by angular offsets.
    pts: list[tuple[float, float]] = []
    az_center = math.radians(view_az_deg)
    elev_center = math.radians(view_elev_deg)
    for azp, elev in zip(az_plot, elev_horizon_deg):
        dx = _wrap_pi(math.radians(azp % 360.0) - az_center)
        dy = math.radians(float(elev)) - elev_center
        x = intr.cx + intr.fx * math.tan(dx)
        y = intr.cy - intr.fy * math.tan(dy)
        pts.append((x, y))
    if len(pts) >= 2:
        draw.line(pts, fill=(80, 170, 255, 255), width=3)

    inside: list[str] = []
    outside: list[str] = []

    for t in turbines:
        tid = str(t.get("id", "WTG"))
        base = np.array(t["base_xyz"], dtype=float)
        hub = np.array([base[0], base[1], base[2] + float(t["tower_height_m"])], dtype=float)
        rotor_r = float(t.get("rotor_diameter_m", 0.0)) * 0.5

        pb = project_point(base, pose, intr)
        ph = project_point(hub, pose, intr)
        if pb is None or ph is None:
            outside.append(tid)
            continue

        ub, vb, _ = pb
        uh, vh, z_hub = ph
        draw.line([(ub, vb), (uh, vh)], fill=(0, 255, 120, 255), width=3)

        if rotor_r > 0:
            r_px = intr.fx * (rotor_r / z_hub)
            draw.ellipse((uh - r_px, vh - r_px, uh + r_px, vh + r_px), outline=(255, 230, 80, 255), width=3)

        in_frame = (0 <= ub < intr.width_px and 0 <= vb < intr.height_px) or (
            0 <= uh < intr.width_px and 0 <= vh < intr.height_px
        )
        if in_frame:
            inside.append(tid)
            base_quota_m = float(base[2])
            tip_quota_m = base_quota_m + float(t["tower_height_m"]) + rotor_r
            visible_height_m = float(t.get("visible_height_m", 0.0) or 0.0)
            label = (
                f"{tid}\n"
                f"quota base: {base_quota_m:.1f} m\n"
                f"quota tip: {tip_quota_m:.1f} m\n"
                f"altezza sporgente: {visible_height_m:.1f} m"
            )
            draw.text((uh + 10, vh - 12), label, fill=(255, 255, 255, 255), font=label_font)
        else:
            outside.append(tid)

    if draw_crosshair:
        c = (255, 255, 255, 180)
        draw.line([(intr.cx - 15, intr.cy), (intr.cx + 15, intr.cy)], fill=c, width=1)
        draw.line([(intr.cx, intr.cy - 15), (intr.cx, intr.cy + 15)], fill=c, width=1)

    im.save(output_path)
    return CameraRenderResult(inside_ids=inside, outside_ids=outside)
