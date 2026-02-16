from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Tuple


Vector3 = Tuple[float, float, float]


@dataclass
class CameraPose:
    position: Vector3
    right: Vector3
    up: Vector3
    forward: Vector3


@dataclass
class CameraIntrinsics:
    fx: float
    fy: float
    cx: float
    cy: float


def _normalize(v: Vector3) -> Vector3:
    n = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    if n == 0:
        raise ValueError("Cannot normalize zero-length vector")
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a: Vector3, b: Vector3) -> Vector3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _sub(a: Vector3, b: Vector3) -> Vector3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vector3, b: Vector3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def compute_look_at_pose(
    camera_position: Vector3,
    look_at_target: Vector3,
    up_world: Vector3 = (0.0, 0.0, 1.0),
) -> CameraPose:
    """Build a right-handed camera basis with +Z in camera-space as forward depth."""
    forward = _normalize(_sub(look_at_target, camera_position))

    # Fallback if forward nearly collinear with world up.
    if abs(_dot(forward, _normalize(up_world))) > 0.999:
        up_world = (0.0, 1.0, 0.0)

    right = _normalize(_cross(forward, up_world))
    up = _normalize(_cross(right, forward))

    return CameraPose(position=camera_position, right=right, up=up, forward=forward)


def compute_intrinsics(
    focal_mm: float,
    sensor_mm: Iterable[float],
    width_px: int,
    height_px: int,
    fov_scale: float = 1.0,
) -> CameraIntrinsics:
    sensor_w, sensor_h = tuple(sensor_mm)
    if sensor_w <= 0 or sensor_h <= 0:
        raise ValueError("Sensor size must be positive")
    if focal_mm <= 0:
        raise ValueError("Focal length must be positive")
    if width_px <= 0 or height_px <= 0:
        raise ValueError("Image dimensions must be positive")
    if fov_scale <= 0:
        raise ValueError("FOV scale must be positive")

    fx = focal_mm * (width_px / sensor_w) * fov_scale
    fy = focal_mm * (height_px / sensor_h) * fov_scale
    cx = width_px / 2.0
    cy = height_px / 2.0
    return CameraIntrinsics(fx=fx, fy=fy, cx=cx, cy=cy)


def world_to_camera(point_world: Vector3, pose: CameraPose) -> Vector3:
    rel = _sub(point_world, pose.position)
    x_cam = _dot(rel, pose.right)
    y_cam = _dot(rel, pose.up)
    z_cam = _dot(rel, pose.forward)
    return (x_cam, y_cam, z_cam)
