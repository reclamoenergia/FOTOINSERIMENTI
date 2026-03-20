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
DebugLogger = Callable[[str], None]
ASYMPTOTE_EPS_RAD = math.radians(0.5)

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
    draw_segments: list[list[Point2D]]
    x_samples: np.ndarray
    y_samples: np.ndarray
    valid_point_count: int
    x_min: float | None
    x_max: float | None
    y_min: float | None
    y_max: float | None


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


@dataclass
class VisiblePartsTurbineLog:
    turbine_id: str
    base_px: Point2D
    hub_px: Point2D
    horizon_y_base: float
    horizon_y_hub: float
    base_visible: bool
    hub_visible: bool
    visible_blade_segments: int
    tower_drawn: bool


def _wrap_pi(rad: float) -> float:
    return (rad + math.pi) % (2.0 * math.pi) - math.pi


def _is_finite_point(point: Point2D) -> bool:
    return math.isfinite(point[0]) and math.isfinite(point[1])


def _build_draw_segments(points: list[Point2D]) -> list[list[Point2D]]:
    segments: list[list[Point2D]] = []
    current: list[Point2D] = []
    for point in points:
        if _is_finite_point(point):
            current.append(point)
            continue
        if len(current) >= 2:
            segments.append(current)
        current = []
    if len(current) >= 2:
        segments.append(current)
    return segments


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

        if abs(dx) >= (math.pi * 0.5 - ASYMPTOTE_EPS_RAD):
            pts.append((float("nan"), float("nan")))
            continue

        x = intr.cx + intr.fx * math.tan(dx)
        y = intr.cy - intr.fy * math.tan(dy)
        pts.append((x, y))

    draw_segments = _build_draw_segments(pts)
    valid_points = [point for point in pts if _is_finite_point(point)]
    if not valid_points:
        return ProjectedSkyline(
            points=pts,
            draw_segments=draw_segments,
            x_samples=np.empty(0, dtype=float),
            y_samples=np.empty(0, dtype=float),
            valid_point_count=0,
            x_min=None,
            x_max=None,
            y_min=None,
            y_max=None,
        )

    x_arr = np.array([p[0] for p in valid_points], dtype=float)
    y_arr = np.array([p[1] for p in valid_points], dtype=float)
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
        draw_segments=draw_segments,
        x_samples=np.array(unique_x, dtype=float),
        y_samples=np.array(unique_y, dtype=float),
        valid_point_count=len(valid_points),
        x_min=float(np.min(x_arr)),
        x_max=float(np.max(x_arr)),
        y_min=float(np.min(y_arr)),
        y_max=float(np.max(y_arr)),
    )


def build_horizon_interpolator(
    skyline: ProjectedSkyline,
    debug_log: DebugLogger | None = None,
) -> Callable[[float], float]:
    if debug_log is not None:
        if skyline.valid_point_count == 0:
            debug_log("[DEBUG] Skyline pixel stats: valid_points=0")
        else:
            debug_log(
                "[DEBUG] Skyline pixel stats: "
                f"valid_points={skyline.valid_point_count} "
                f"x_min={skyline.x_min:.2f} x_max={skyline.x_max:.2f} "
                f"y_min={skyline.y_min:.2f} y_max={skyline.y_max:.2f}"
            )

    if len(skyline.x_samples) == 0:
        return lambda _x: float("inf")

    if len(skyline.x_samples) == 1:
        horizon_y = float(skyline.y_samples[0])
        return lambda _x: horizon_y

    x_min = float(skyline.x_samples[0])
    x_max = float(skyline.x_samples[-1])
    y_left = float(skyline.y_samples[0])
    y_right = float(skyline.y_samples[-1])

    def _horizon_y(x_value: float) -> float:
        if x_value < x_min:
            return y_left
        if x_value > x_max:
            return y_right
        return float(np.interp(x_value, skyline.x_samples, skyline.y_samples))

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
    debug_log: DebugLogger | None = None,
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
        horizon_y=build_horizon_interpolator(skyline, debug_log=debug_log),
    )


def _new_image(intr: CameraIntrinsics, transparent: bool) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    bg = (0, 0, 0, 0) if transparent else (0, 0, 0, 255)
    image = Image.new("RGBA", (intr.width_px, intr.height_px), bg)
    return image, ImageDraw.Draw(image)


def _draw_skyline(draw: ImageDraw.ImageDraw, skyline: ProjectedSkyline) -> None:
    for segment in skyline.draw_segments:
        if len(segment) >= 2:
            draw.line(segment, fill=SKYLINE_COLOR, width=3)


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


def is_point_above_horizon(point: Point2D, horizon_y_func: Callable[[float], float]) -> bool:
    return point[1] < horizon_y_func(point[0])


def _difference_to_horizon(point_a: Point2D, point_b: Point2D, t_value: float, horizon_y_func: Callable[[float], float]) -> float:
    x = point_a[0] + (point_b[0] - point_a[0]) * t_value
    y = point_a[1] + (point_b[1] - point_a[1]) * t_value
    return y - horizon_y_func(x)


def _solve_segment_horizon_intersection(
    point_a: Point2D,
    point_b: Point2D,
    horizon_y_func: Callable[[float], float],
    t0: float,
    t1: float,
) -> float:
    left = t0
    right = t1
    d_left = _difference_to_horizon(point_a, point_b, left, horizon_y_func)
    d_right = _difference_to_horizon(point_a, point_b, right, horizon_y_func)

    if math.isclose(d_left, 0.0, abs_tol=1e-6):
        return left
    if math.isclose(d_right, 0.0, abs_tol=1e-6):
        return right

    for _ in range(60):
        mid = (left + right) * 0.5
        d_mid = _difference_to_horizon(point_a, point_b, mid, horizon_y_func)
        if math.isclose(d_mid, 0.0, abs_tol=1e-6):
            return mid
        if d_left * d_mid <= 0.0:
            right = mid
            d_right = d_mid
        else:
            left = mid
            d_left = d_mid

    return (left + right) * 0.5


def clip_segment_against_horizon(
    point_a: Point2D,
    point_b: Point2D,
    horizon_y_func: Callable[[float], float],
    skyline_x_breaks: np.ndarray | None = None,
) -> list[Segment2D]:
    dx = point_b[0] - point_a[0]
    dy = point_b[1] - point_a[1]
    params: list[float] = [0.0, 1.0]
    if skyline_x_breaks is not None and abs(dx) > 1e-9:
        x_min = min(point_a[0], point_b[0])
        x_max = max(point_a[0], point_b[0])
        for x_break in skyline_x_breaks[1:-1]:
            if x_min < float(x_break) < x_max:
                params.append((float(x_break) - point_a[0]) / dx)

    params = sorted({min(1.0, max(0.0, value)) for value in params})
    visible_segments: list[Segment2D] = []

    for t0, t1 in zip(params[:-1], params[1:]):
        if t1 - t0 <= 1e-9:
            continue

        point_0 = (point_a[0] + dx * t0, point_a[1] + dy * t0)
        point_1 = (point_a[0] + dx * t1, point_a[1] + dy * t1)
        visible_0 = is_point_above_horizon(point_0, horizon_y_func)
        visible_1 = is_point_above_horizon(point_1, horizon_y_func)

        if visible_0 and visible_1:
            if math.hypot(point_1[0] - point_0[0], point_1[1] - point_0[1]) > 1e-6:
                visible_segments.append((point_0, point_1))
            continue

        if (not visible_0) and (not visible_1):
            continue

        tm = (t0 + t1) * 0.5
        intersection_t = _solve_segment_horizon_intersection(point_a, point_b, horizon_y_func, t0, t1)
        intersection = (point_a[0] + dx * intersection_t, point_a[1] + dy * intersection_t)
        segment = (point_0, intersection) if visible_0 else (intersection, point_1)
        if math.hypot(segment[1][0] - segment[0][0], segment[1][1] - segment[0][1]) > 1e-6:
            visible_segments.append(segment)

    return visible_segments


def _draw_visible_segments(draw: ImageDraw.ImageDraw, segments: list[Segment2D], color: Color, width: int) -> int:
    drawn_count = 0
    for start, end in segments:
        if math.hypot(end[0] - start[0], end[1] - start[1]) <= 1e-6:
            continue
        draw.line([start, end], fill=color, width=width)
        drawn_count += 1
    return drawn_count


def render_visible_parts_view_png(
    output_path: str | Path,
    scene: CameraRenderScene,
    transparent: bool = False,
    blade_rotation_deg: float = 0.0,
    debug_log: DebugLogger | None = None,
) -> list[VisiblePartsTurbineLog]:
    image, draw = _new_image(scene.intr, transparent)
    _draw_skyline(draw, scene.skyline)

    turbine_logs: list[VisiblePartsTurbineLog] = []
    for turbine in scene.turbines:
        horizon_y_base = scene.horizon_y(turbine.base_point[0])
        horizon_y_hub = scene.horizon_y(turbine.hub_point[0])
        base_visible = is_point_above_horizon(turbine.base_point, scene.horizon_y)
        hub_visible = is_point_above_horizon(turbine.hub_point, scene.horizon_y)

        tower_segments = clip_segment_against_horizon(
            turbine.base_point,
            turbine.hub_point,
            scene.horizon_y,
            skyline_x_breaks=scene.skyline.x_samples,
        )
        tower_drawn = _draw_visible_segments(draw, tower_segments, color=TOWER_COLOR, width=3) > 0

        visible_blade_segments = 0
        if turbine.rotor_radius_px > 0:
            hub_x, hub_y = turbine.hub_point
            for blade_angle_deg in DEFAULT_BLADE_ANGLES_DEG:
                angle_rad = math.radians(blade_angle_deg + blade_rotation_deg)
                tip = (
                    hub_x + turbine.rotor_radius_px * math.cos(angle_rad),
                    hub_y + turbine.rotor_radius_px * math.sin(angle_rad),
                )
                blade_segments = clip_segment_against_horizon(
                    turbine.hub_point,
                    tip,
                    scene.horizon_y,
                    skyline_x_breaks=scene.skyline.x_samples,
                )
                visible_blade_segments += _draw_visible_segments(draw, blade_segments, color=ROTOR_COLOR, width=3)

        item_log = VisiblePartsTurbineLog(
            turbine_id=turbine.turbine_id,
            base_px=turbine.base_point,
            hub_px=turbine.hub_point,
            horizon_y_base=float(horizon_y_base),
            horizon_y_hub=float(horizon_y_hub),
            base_visible=base_visible,
            hub_visible=hub_visible,
            visible_blade_segments=visible_blade_segments,
            tower_drawn=tower_drawn,
        )
        turbine_logs.append(item_log)
        if debug_log is not None:
            debug_log(
                f"[DEBUG] visible_parts {item_log.turbine_id}: "
                f"base_px=({item_log.base_px[0]:.2f},{item_log.base_px[1]:.2f}) "
                f"hub_px=({item_log.hub_px[0]:.2f},{item_log.hub_px[1]:.2f}) "
                f"horizon_y(base_x)={item_log.horizon_y_base:.2f} "
                f"horizon_y(hub_x)={item_log.horizon_y_hub:.2f} "
                f"base_visible={item_log.base_visible} "
                f"hub_visible={item_log.hub_visible} "
                f"tower_drawn={item_log.tower_drawn} "
                f"visible_blade_segments={item_log.visible_blade_segments}"
            )

    image.save(output_path)
    return turbine_logs


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
    debug_log: DebugLogger | None = None,
) -> CameraRenderResult:
    scene = compute_camera_render_scene(
        intr=intr,
        pose=pose,
        az_plot=az_plot,
        elev_horizon_deg=elev_horizon_deg,
        view_az_deg=view_az_deg,
        view_elev_deg=view_elev_deg,
        turbines=turbines,
        debug_log=debug_log,
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
