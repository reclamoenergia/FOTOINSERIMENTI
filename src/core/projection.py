from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .camera import CameraIntrinsics, CameraPose, world_to_camera


Vector3 = Tuple[float, float, float]


@dataclass
class ProjectionResult:
    pixel: Tuple[float, float]
    depth: float


def project_world_point(
    point_world: Vector3,
    pose: CameraPose,
    intrinsics: CameraIntrinsics,
) -> ProjectionResult | None:
    x_cam, y_cam, z_cam = world_to_camera(point_world, pose)
    if z_cam <= 1e-6:
        return None

    u = intrinsics.fx * (x_cam / z_cam) + intrinsics.cx
    v = intrinsics.cy - intrinsics.fy * (y_cam / z_cam)
    return ProjectionResult(pixel=(u, v), depth=z_cam)
