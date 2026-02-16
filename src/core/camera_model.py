from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np


@dataclass
class CameraIntrinsics:
    fx: float
    fy: float
    cx: float
    cy: float
    width_px: int
    height_px: int


@dataclass
class CameraPose:
    position: np.ndarray
    right: np.ndarray
    up: np.ndarray
    forward: np.ndarray


def _normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n <= 0:
        raise ValueError("Cannot normalize a zero vector")
    return v / n


def intrinsics_from_photo(
    focal_mm: float,
    sensor_mm: Iterable[float],
    width_px: int,
    height_px: int,
    fov_scale: float = 1.0,
) -> CameraIntrinsics:
    sensor_w, sensor_h = tuple(sensor_mm)
    if focal_mm <= 0 or sensor_w <= 0 or sensor_h <= 0:
        raise ValueError("Focal and sensor size must be positive")
    if width_px <= 0 or height_px <= 0:
        raise ValueError("Output size must be positive")
    if fov_scale <= 0:
        raise ValueError("FOV scale must be positive")

    fx = focal_mm * (width_px / sensor_w) * fov_scale
    fy = focal_mm * (height_px / sensor_h) * fov_scale
    return CameraIntrinsics(fx=fx, fy=fy, cx=width_px / 2.0, cy=height_px / 2.0, width_px=width_px, height_px=height_px)


def forward_from_az_el_deg(azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    c = math.cos(el)
    return np.array([c * math.sin(az), c * math.cos(az), math.sin(el)], dtype=float)


def camera_pose_from_forward(camera_pos: np.ndarray, forward: np.ndarray, up_world: np.ndarray | None = None) -> CameraPose:
    if up_world is None:
        up_world = np.array([0.0, 0.0, 1.0], dtype=float)
    forward_n = _normalize(forward)
    up_world_n = _normalize(up_world)

    if abs(float(np.dot(forward_n, up_world_n))) > 0.999:
        up_world_n = np.array([0.0, 1.0, 0.0], dtype=float)

    right = _normalize(np.cross(forward_n, up_world_n))
    up = _normalize(np.cross(right, forward_n))
    return CameraPose(position=np.array(camera_pos, dtype=float), right=right, up=up, forward=forward_n)


def world_to_camera(point_world: np.ndarray, pose: CameraPose) -> np.ndarray:
    rel = np.array(point_world, dtype=float) - pose.position
    x_cam = float(np.dot(rel, pose.right))
    y_cam = float(np.dot(rel, pose.up))
    z_cam = float(np.dot(rel, pose.forward))
    return np.array([x_cam, y_cam, z_cam], dtype=float)


def project_point(point_world: np.ndarray, pose: CameraPose, intr: CameraIntrinsics) -> tuple[float, float, float] | None:
    x_cam, y_cam, z_cam = world_to_camera(point_world, pose)
    if z_cam <= 1e-6:
        return None
    u = intr.cx + intr.fx * (x_cam / z_cam)
    v = intr.cy - intr.fy * (y_cam / z_cam)
    return (u, v, z_cam)


def hfov_vfov_deg(focal_mm: float, sensor_w_mm: float, sensor_h_mm: float) -> tuple[float, float]:
    h = math.degrees(2.0 * math.atan(sensor_w_mm / (2.0 * focal_mm)))
    v = math.degrees(2.0 * math.atan(sensor_h_mm / (2.0 * focal_mm)))
    return h, v
