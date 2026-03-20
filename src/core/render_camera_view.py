from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .camera_model import CameraIntrinsics, CameraPose, project_point


Color = tuple[int, int, int, int]
Point2D = tuple[float, float]
Segment2D = tuple[Point2D, Point2D]

SKYLINE_COLOR: Color = (80, 170, 255, 255)
TOWER_COLOR: Color = (0, 255, 120, 255)
ROTOR_COLOR: Color = (255, 230, 80, 255)
CROSSHAIR_COLOR: Color = (255, 255, 255, 180)
TEXT_COLOR: Color = (255, 255, 255, 255)
DEFAULT_BLADE_ANGLES_DEG: tuple[float, float, float] = (-90.0, 30.0, 150.0)


@dataclass
class CameraRenderResult:
    inside_ids: list[str]
    outside_ids: list[str]


@dataclass
class ProjectedSkyline:
    points: list[Point2D]
    x_samples: np.ndarray
    y_samples: np.ndarray


@dataclass
class ProjectedTurbine:
    turbine: dict[str, Any]
    turbine_id: str
    base_point: Point2D
    hub_point: Point2D
    hub_depth: float
    rotor_radius_px: float
    in_frame: bool


@dataclass
class CameraRenderScene:
    intr: CameraIntrinsics
    pose: CameraPose
    skyline: ProjectedSkyline
    turbines: list[ProjectedTurbine]
    horizon_y: Callable[[float], float]


def _wrap_pi(rad: float) -> float:
    return (rad + math.pi) % (2.0 * math.pi) - math.pi


def _project_skyline(
    intr: CameraIntrinsics,
    az_plot: np.ndarray,
    elev_horizon_deg: np.ndarray,
    view_az_deg: float,
    view_elev_deg: float,
) -> ProjectedSkyline:
    pts: list[Point2D] = []
    az_center = math.radians(view_az_deg)
    elev_center = math.radians(view_elev_deg)
    for azp, elev in zip(az_plot, elev_horizon_deg):
        dx = _wrap_pi(math.radians(azp % 360.0) - az_center)
        dy = math.radians(float(elev)) - elev_center
        x = intr.cx + intr.fx * math.tan(dx)
        y = intr.cy - intr.fy * math.tan(dy)
        pts.append((x, y))

    if not pts:
        return ProjectedSkyline(points=[], x_samples=np.empty(0, dtype=float), y_samples=np.empty(0, dtype=float))

    x_arr = np.array([p[0] for p in pts], dtype=float)
    y_arr = np.array([p[1] for p in pts], dtype=float)
    order = np.argsort(x_arr, kind="mergesort")
    x_sorted = x_arr[order]
    y_sorted = y_arr[order]

    unique_x: list[float] = []
    unique_y: list[float] = []
    for x_val, y_val in zip(x_sorted, y_sorted):
        if unique_x and math.isclose(x_val, unique_x[-1], abs_tol=1e-9):
            unique_y[-1] = min(unique_y[-1], float(y_val))
        else:
            unique_x.append(float(x_val))
            unique_y.append(float(y_val))

    return ProjectedSkyline(
        points=pts,
        x_samples=np.array(unique_x, dtype=float),
        y_samples=np.array(unique_y, dtype=float),
    )


def build_horizon_interpolator(skyline: ProjectedSkyline) -> Callable[[float], float]:
    if len(skyline.x_samples) == 0:
        return lambda _x: float("inf")

    if len(skyline.x_samples) == 1:
        horizon_y = float(skyline.y_samples[0])
        return lambda _x: horizon_y

    def _horizon_y(x_value: float) -> float:
        return float(np.interp(x_value, skyline.x_samples, skyline.y_samples, left=skyline.y_samples[0], right=skyline.y_samples[-1]))

    return _horizon_y


def _point_in_frame(point: Point2D, intr: CameraIntrinsics) -> bool:
    x, y = point
    return 0 <= x < intr.width_px and 0 <= y < intr.height_px


def _project_turbines(
    intr: CameraIntrinsics,
    pose: CameraPose,
    turbines: list[dict[str, Any]],
) -> list[ProjectedTurbine]:
    projected: list[ProjectedTurbine] = []
    for turbine in turbines:
        turbine_id = str(turbine.get("id", "WTG"))
        base = np.array(turbine["base_xyz"], dtype=float)
        hub = np.array([base[0], base[1], base[2] + float(turbine["tower_height_m"])], dtype=float)
        rotor_radius_m = float(turbine.get("rotor_diameter_m", 0.0)) * 0.5

        base_proj = project_point(base, pose, intr)
        hub_proj = project_point(hub, pose, intr)
        if base_proj is None or hub_proj is None:
            continue

        ub, vb, _ = base_proj
        uh, vh, hub_depth = hub_proj
        rotor_radius_px = intr.fx * (rotor_radius_m / hub_depth) if rotor_radius_m > 0 else 0.0
        in_frame = (
            _point_in_frame((ub, vb), intr)
            or _point_in_frame((uh, vh), intr)
            or _point_in_frame((uh + rotor_radius_px, vh), intr)
            or _point_in_frame((uh - rotor_radius_px, vh), intr)
            or _point_in_frame((uh, vh + rotor_radius_px), intr)
            or _point_in_frame((uh, vh - rotor_radius_px), intr)
        )

        projected.append(
            ProjectedTurbine(
                turbine=turbine,
                turbine_id=turbine_id,
                base_point=(ub, vb),
                hub_point=(uh, vh),
                hub_depth=float(hub_depth),
                rotor_radius_px=float(rotor_radius_px),
                in_frame=in_frame,
            )
        )
    return projected


def compute_camera_render_scene(
    intr: CameraIntrinsics,
    pose: CameraPose,
    az_plot: np.ndarray,
    elev_horizon_deg: np.ndarray,
    view_az_deg: float,
    view_elev_deg: float,
    turbines: list[dict[str, Any]],
) -> CameraRenderScene:
    skyline = _project_skyline(
        intr=intr,
        az_plot=az_plot,
        elev_horizon_deg=elev_horizon_deg,
        view_az_deg=view_az_deg,
        view_elev_deg=view_elev_deg,
    )
    return CameraRenderScene(
        intr=intr,
        pose=pose,
        skyline=skyline,
        turbines=_project_turbines(intr=intr, pose=pose, turbines=turbines),
        horizon_y=build_horizon_interpolator(skyline),
    )


def _new_image(intr: CameraIntrinsics, transparent: bool) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    bg = (0, 0, 0, 0) if transparent else (0, 0, 0, 255)
    image = Image.new("RGBA", (intr.width_px, intr.height_px), bg)
    return image, ImageDraw.Draw(image)


def _draw_skyline(draw: ImageDraw.ImageDraw, skyline: ProjectedSkyline) -> None:
    if len(skyline.points) >= 2:
        draw.line(skyline.points, fill=SKYLINE_COLOR, width=3)


def _load_label_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", 20)
    except OSError:
        return ImageFont.load_default()


def _render_camera_scene(
    output_path: str | Path,
    scene: CameraRenderScene,
    transparent: bool = False,
    draw_crosshair: bool = True,
) -> CameraRenderResult:
    image, draw = _new_image(scene.intr, transparent)
    label_font = _load_label_font()
    _draw_skyline(draw, scene.skyline)

    inside: list[str] = []
    outside: list[str] = []

    for turbine in scene.turbines:
        draw.line([turbine.base_point, turbine.hub_point], fill=TOWER_COLOR, width=3)

        if turbine.rotor_radius_px > 0:
            uh, vh = turbine.hub_point
            r_px = turbine.rotor_radius_px
            draw.ellipse((uh - r_px, vh - r_px, uh + r_px, vh + r_px), outline=ROTOR_COLOR, width=3)

        if turbine.in_frame:
            inside.append(turbine.turbine_id)
            base_quota_m = float(turbine.turbine["base_xyz"][2])
            rotor_radius_m = float(turbine.turbine.get("rotor_diameter_m", 0.0)) * 0.5
            tip_quota_m = base_quota_m + float(turbine.turbine["tower_height_m"]) + rotor_radius_m
            visible_height_m = float(turbine.turbine.get("visible_height_m", 0.0) or 0.0)
            label = (
                f"{turbine.turbine_id}\n"
                f"quota base: {base_quota_m:.1f} m\n"
                f"quota tip: {tip_quota_m:.1f} m\n"
                f"altezza sporgente: {visible_height_m:.1f} m"
            )
            draw.text((turbine.hub_point[0] + 10, turbine.hub_point[1] - 12), label, fill=TEXT_COLOR, font=label_font)
        else:
            outside.append(turbine.turbine_id)

    if draw_crosshair:
        draw.line([(scene.intr.cx - 15, scene.intr.cy), (scene.intr.cx + 15, scene.intr.cy)], fill=CROSSHAIR_COLOR, width=1)
        draw.line([(scene.intr.cx, scene.intr.cy - 15), (scene.intr.cx, scene.intr.cy + 15)], fill=CROSSHAIR_COLOR, width=1)

    image.save(output_path)
    return CameraRenderResult(inside_ids=inside, outside_ids=outside)


def _difference_to_horizon(scene: CameraRenderScene, point_a: Point2D, point_b: Point2D, t_value: float) -> float:
    x = point_a[0] + (point_b[0] - point_a[0]) * t_value
    y = point_a[1] + (point_b[1] - point_a[1]) * t_value
    return y - scene.horizon_y(x)


def _solve_segment_horizon_intersection(scene: CameraRenderScene, point_a: Point2D, point_b: Point2D, t0: float, t1: float) -> float:
    d0 = _difference_to_horizon(scene, point_a, point_b, t0)
    d1 = _difference_to_horizon(scene, point_a, point_b, t1)
    if math.isclose(d0, 0.0, abs_tol=1e-6):
        return t0
    if math.isclose(d1, 0.0, abs_tol=1e-6):
        return t1

    left = t0
    right = t1
    for _ in range(40):
        mid = (left + right) * 0.5
        dm = _difference_to_horizon(scene, point_a, point_b, mid)
        if math.isclose(dm, 0.0, abs_tol=1e-6):
            return mid
        if d0 * dm <= 0.0:
            right = mid
            d1 = dm
        else:
            left = mid
            d0 = dm
    return (left + right) * 0.5


def clip_segment_against_horizon(
    point_a: Point2D,
    point_b: Point2D,
    scene: CameraRenderScene,
) -> list[Segment2D]:
    dx = point_b[0] - point_a[0]
    params: list[float] = [0.0, 1.0]
    if abs(dx) > 1e-9:
        x_min = min(point_a[0], point_b[0])
        x_max = max(point_a[0], point_b[0])
        for x_break in scene.skyline.x_samples[1:-1]:
            if x_min < x_break < x_max:
                params.append((float(x_break) - point_a[0]) / dx)

    params = sorted(min(1.0, max(0.0, p)) for p in params)

    visible_segments: list[Segment2D] = []
    for t0, t1 in zip(params[:-1], params[1:]):
        if t1 - t0 <= 1e-9:
            continue
        tm = (t0 + t1) * 0.5
        if _difference_to_horizon(scene, point_a, point_b, tm) >= 0.0:
            continue

        start_t = t0
        end_t = t1
        d0 = _difference_to_horizon(scene, point_a, point_b, t0)
        d1 = _difference_to_horizon(scene, point_a, point_b, t1)
        if d0 >= 0.0:
            start_t = _solve_segment_horizon_intersection(scene, point_a, point_b, t0, tm)
        if d1 >= 0.0:
            end_t = _solve_segment_horizon_intersection(scene, point_a, point_b, tm, t1)

        start = (
            point_a[0] + dx * start_t,
            point_a[1] + (point_b[1] - point_a[1]) * start_t,
        )
        end = (
            point_a[0] + dx * end_t,
            point_a[1] + (point_b[1] - point_a[1]) * end_t,
        )
        if math.hypot(end[0] - start[0], end[1] - start[1]) > 1e-6:
            visible_segments.append((start, end))

    return visible_segments


def _draw_visible_segment_list(draw: ImageDraw.ImageDraw, segments: list[Segment2D], color: Color, width: int) -> None:
    for start, end in segments:
        draw.line([start, end], fill=color, width=width)


def render_visible_parts_view_png(
    output_path: str | Path,
    scene: CameraRenderScene,
    transparent: bool = False,
    blade_rotation_deg: float = 0.0,
) -> None:
    image, draw = _new_image(scene.intr, transparent)
    _draw_skyline(draw, scene.skyline)

    for turbine in scene.turbines:
        tower_segments = clip_segment_against_horizon(turbine.base_point, turbine.hub_point, scene)
        _draw_visible_segment_list(draw, tower_segments, color=TOWER_COLOR, width=3)

        if turbine.rotor_radius_px <= 0:
            continue

        hub_x, hub_y = turbine.hub_point
        for blade_angle_deg in DEFAULT_BLADE_ANGLES_DEG:
            angle_rad = math.radians(blade_angle_deg + blade_rotation_deg)
            tip = (
                hub_x + turbine.rotor_radius_px * math.cos(angle_rad),
                hub_y + turbine.rotor_radius_px * math.sin(angle_rad),
            )
            blade_segments = clip_segment_against_horizon(turbine.hub_point, tip, scene)
            _draw_visible_segment_list(draw, blade_segments, color=ROTOR_COLOR, width=3)

    image.save(output_path)


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
    scene = compute_camera_render_scene(
        intr=intr,
        pose=pose,
        az_plot=az_plot,
        elev_horizon_deg=elev_horizon_deg,
        view_az_deg=view_az_deg,
        view_elev_deg=view_elev_deg,
        turbines=turbines,
    )
    return render_camera_view_scene(
        output_path=output_path,
        scene=scene,
        transparent=transparent,
        draw_crosshair=draw_crosshair,
        all_turbine_ids=[str(t.get("id", "WTG")) for t in turbines],
    )


def render_camera_view_scene(
    output_path: str | Path,
    scene: CameraRenderScene,
    transparent: bool = False,
    draw_crosshair: bool = True,
    all_turbine_ids: list[str] | None = None,
) -> CameraRenderResult:
    result = _render_camera_scene(
        output_path=output_path,
        scene=scene,
        transparent=transparent,
        draw_crosshair=draw_crosshair,
    )
    if all_turbine_ids is None:
        return result

    inside_set = set(result.inside_ids)
    outside_ids = [tid for tid in all_turbine_ids if tid not in inside_set]
    inside_ids = [tid for tid in all_turbine_ids if tid in inside_set]
    return CameraRenderResult(inside_ids=inside_ids, outside_ids=outside_ids)
