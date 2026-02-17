from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .camera import CameraIntrinsics, compute_intrinsics, compute_look_at_pose
from .projection import project_world_point


Vector3 = Tuple[float, float, float]


@dataclass
class CropRect:
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0

    @property
    def enabled(self) -> bool:
        return self.w > 0 and self.h > 0


@dataclass
class Turbine:
    turbine_id: str
    base_xyz: Vector3
    tower_height_m: float
    rotor_diameter_m: float


@dataclass
class SceneConfig:
    camera_position: Vector3
    focal_mm: float
    sensor_mm: Tuple[float, float]
    image_width: int
    image_height: int
    crop: CropRect
    fov_scale: float
    turbines: List[Turbine]


@dataclass
class OverlayStyle:
    line_thickness: int = 3
    circle_thickness: int = 3
    text_thickness: int = 1
    draw_ids: bool = True
    font_size: int = 18
    line_color: str = "#00FF00"
    circle_color: str = "#FFA500"
    text_color: str = "#FFFFFF"


@dataclass
class RenderLogEntry:
    turbine_id: str
    reason: str


@dataclass
class RenderSummary:
    processed: int
    drawn: int
    skipped: int
    skipped_items: List[RenderLogEntry]
    output_path: Path


def _as_vector3(values: Any, field_name: str) -> Vector3:
    if not isinstance(values, list) or len(values) != 3:
        raise ValueError(f"{field_name} must be an array with 3 numbers")
    return (float(values[0]), float(values[1]), float(values[2]))


def load_scene_config(json_path: str | Path) -> SceneConfig:
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    camera = payload.get("camera", {})
    image = payload.get("image", {})
    turbines_data = payload.get("turbines", [])

    sensor_mm = tuple(camera.get("sensor_mm", [36.0, 24.0]))
    if len(sensor_mm) != 2:
        raise ValueError("camera.sensor_mm must contain two values")

    crop_payload = image.get("crop", {}) or {}
    crop = CropRect(
        x=int(crop_payload.get("x", 0)),
        y=int(crop_payload.get("y", 0)),
        w=int(crop_payload.get("w", 0)),
        h=int(crop_payload.get("h", 0)),
    )

    turbines: List[Turbine] = []
    for item in turbines_data:
        turbines.append(
            Turbine(
                turbine_id=str(item.get("id", "UNKNOWN")),
                base_xyz=_as_vector3(item.get("base_xyz"), "turbines.base_xyz"),
                tower_height_m=float(item.get("tower_height_m", 0.0)),
                rotor_diameter_m=float(item.get("rotor_diameter_m", 0.0)),
            )
        )

    return SceneConfig(
        camera_position=_as_vector3(camera.get("position_xyz"), "camera.position_xyz"),
        focal_mm=float(camera.get("focal_mm", 50.0)),
        sensor_mm=(float(sensor_mm[0]), float(sensor_mm[1])),
        image_width=int(image.get("width_px", 0)),
        image_height=int(image.get("height_px", 0)),
        crop=crop,
        fov_scale=float(image.get("fov_scale", 1.0)),
        turbines=turbines,
    )


def _centroid(points: List[Vector3]) -> Vector3:
    n = len(points)
    if n == 0:
        raise ValueError("Cannot compute centroid of empty list")
    sx = sum(p[0] for p in points)
    sy = sum(p[1] for p in points)
    sz = sum(p[2] for p in points)
    return (sx / n, sy / n, sz / n)


def _in_frame(u: float, v: float, width: int, height: int) -> bool:
    return 0 <= u < width and 0 <= v < height


def _validate_scene(scene: SceneConfig, width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive")
    if scene.focal_mm <= 0:
        raise ValueError("camera.focal_mm must be > 0")
    if scene.sensor_mm[0] <= 0 or scene.sensor_mm[1] <= 0:
        raise ValueError("camera.sensor_mm values must be > 0")
    if scene.fov_scale <= 0:
        raise ValueError("image.fov_scale must be > 0")
    if not scene.turbines:
        raise ValueError("No turbines in input")

    if scene.crop.x < 0 or scene.crop.y < 0 or scene.crop.w < 0 or scene.crop.h < 0:
        raise ValueError("crop values must be >= 0")
    if scene.crop.enabled and (scene.crop.x + scene.crop.w > width or scene.crop.y + scene.crop.h > height):
        raise ValueError("crop rectangle exceeds image bounds")


def render_overlay(
    scene: SceneConfig,
    output_path: str | Path,
    style: Optional[OverlayStyle] = None,
    image_override_size: Optional[Tuple[int, int]] = None,
) -> RenderSummary:
    style = style or OverlayStyle()
    width = image_override_size[0] if image_override_size else scene.image_width
    height = image_override_size[1] if image_override_size else scene.image_height

    _validate_scene(scene, width, height)

    hub_points = [
        (t.base_xyz[0], t.base_xyz[1], t.base_xyz[2] + t.tower_height_m) for t in scene.turbines
    ]

    pose = compute_look_at_pose(scene.camera_position, _centroid(hub_points))
    intrinsics: CameraIntrinsics = compute_intrinsics(
        focal_mm=scene.focal_mm,
        sensor_mm=scene.sensor_mm,
        width_px=width,
        height_px=height,
        fov_scale=scene.fov_scale,
    )

    if scene.crop.enabled:
        out_w, out_h = scene.crop.w, scene.crop.h
    else:
        out_w, out_h = width, height

    overlay = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default()

    skipped_items: List[RenderLogEntry] = []
    drawn = 0

    for turbine in scene.turbines:
        base = turbine.base_xyz
        hub = (base[0], base[1], base[2] + turbine.tower_height_m)

        base_proj = project_world_point(base, pose, intrinsics)
        hub_proj = project_world_point(hub, pose, intrinsics)

        if base_proj is None or hub_proj is None:
            skipped_items.append(RenderLogEntry(turbine.turbine_id, "dietro camera"))
            continue

        if turbine.tower_height_m <= 0:
            skipped_items.append(RenderLogEntry(turbine.turbine_id, "altezza torre non valida"))
            continue
        if turbine.rotor_diameter_m <= 0:
            skipped_items.append(RenderLogEntry(turbine.turbine_id, "rotore non valido"))
            continue

        u_base, v_base = base_proj.pixel
        u_hub, v_hub = hub_proj.pixel
        radius_px = intrinsics.fx * ((turbine.rotor_diameter_m / 2.0) / hub_proj.depth)

        if scene.crop.enabled:
            u_base -= scene.crop.x
            v_base -= scene.crop.y
            u_hub -= scene.crop.x
            v_hub -= scene.crop.y
            frame_w, frame_h = scene.crop.w, scene.crop.h
        else:
            frame_w, frame_h = width, height

        visible = (
            _in_frame(u_base, v_base, frame_w, frame_h)
            or _in_frame(u_hub, v_hub, frame_w, frame_h)
            or _in_frame(u_hub + radius_px, v_hub, frame_w, frame_h)
            or _in_frame(u_hub - radius_px, v_hub, frame_w, frame_h)
            or _in_frame(u_hub, v_hub + radius_px, frame_w, frame_h)
            or _in_frame(u_hub, v_hub - radius_px, frame_w, frame_h)
        )

        if not visible:
            skipped_items.append(RenderLogEntry(turbine.turbine_id, "fuori frame"))
            continue

        draw.line(
            [(u_base, v_base), (u_hub, v_hub)],
            fill=style.line_color,
            width=max(1, style.line_thickness),
        )

        draw.ellipse(
            [
                (u_hub - radius_px, v_hub - radius_px),
                (u_hub + radius_px, v_hub + radius_px),
            ],
            outline=style.circle_color,
            width=max(1, style.circle_thickness),
        )

        if style.draw_ids:
            draw.text(
                (u_hub + 8, v_hub + 8),
                turbine.turbine_id,
                fill=style.text_color,
                font=font,
                stroke_width=max(0, style.text_thickness),
            )

        drawn += 1

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(output_path, format="PNG")

    return RenderSummary(
        processed=len(scene.turbines),
        drawn=drawn,
        skipped=len(skipped_items),
        skipped_items=skipped_items,
        output_path=output_path,
    )


def summary_to_lines(summary: RenderSummary) -> List[str]:
    lines = [
        f"Turbine processate: {summary.processed}",
        f"Turbine disegnate: {summary.drawn}",
        f"Turbine scartate: {summary.skipped}",
        f"Output: {summary.output_path}",
    ]
    if summary.skipped_items:
        lines.append("Dettaglio scarti:")
        lines.extend([f"- {item.turbine_id}: {item.reason}" for item in summary.skipped_items])
    return lines
