from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from src.core.camera_model import CameraIntrinsics, CameraPose
from src.core.render_camera_view import (
    CameraRenderScene,
    ProjectedSkyline,
    ProjectedTurbine,
    clip_segment_against_horizon,
    render_camera_view_scene,
    render_visible_parts_view_png,
)


class RenderCameraViewTests(unittest.TestCase):
    def test_clip_segment_against_horizon_keeps_only_visible_part(self) -> None:
        horizon_y = lambda _x: 100.0

        fully_visible = clip_segment_against_horizon((10.0, 80.0), (20.0, 90.0), horizon_y)
        self.assertEqual(fully_visible, ((10.0, 80.0), (20.0, 90.0)))

        fully_hidden = clip_segment_against_horizon((10.0, 120.0), (20.0, 140.0), horizon_y)
        self.assertIsNone(fully_hidden)

        clipped = clip_segment_against_horizon((10.0, 140.0), (10.0, 60.0), horizon_y)
        self.assertIsNotNone(clipped)
        start, end = clipped  # type: ignore[misc]
        self.assertAlmostEqual(start[0], 10.0, places=4)
        self.assertAlmostEqual(start[1], 100.0, places=3)
        self.assertAlmostEqual(end[0], 10.0, places=4)
        self.assertAlmostEqual(end[1], 60.0, places=4)

    def test_render_visible_parts_view_draws_skyline_and_visible_wtg_parts(self) -> None:
        intr = CameraIntrinsics(fx=100.0, fy=100.0, cx=100.0, cy=100.0, width_px=200, height_px=200)
        scene = CameraRenderScene(
            intr=intr,
            pose=CameraPose(
                position=np.zeros(3, dtype=float),
                right=np.array([1.0, 0.0, 0.0], dtype=float),
                up=np.array([0.0, 1.0, 0.0], dtype=float),
                forward=np.array([0.0, 0.0, 1.0], dtype=float),
            ),
            skyline=ProjectedSkyline(
                points=[(0.0, 100.0), (199.0, 100.0)],
                draw_segments=[[(0.0, 100.0), (199.0, 100.0)]],
                x_samples=np.array([0.0, 199.0], dtype=float),
                y_samples=np.array([100.0, 100.0], dtype=float),
                valid_point_count=2,
                x_min=0.0,
                x_max=199.0,
                y_min=100.0,
                y_max=100.0,
            ),
            turbines=[
                ProjectedTurbine(
                    turbine={"id": "WTG01", "base_xyz": [0.0, 0.0, 0.0], "tower_height_m": 100.0, "rotor_diameter_m": 80.0},
                    turbine_id="WTG01",
                    base_point=(100.0, 150.0),
                    hub_point=(100.0, 60.0),
                    hub_depth=1000.0,
                    rotor_radius_px=40.0,
                    in_frame=True,
                )
            ],
            horizon_y=lambda _x: 100.0,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "visible_parts.png"
            turbine_logs = render_visible_parts_view_png(out_path, scene, transparent=False)
            image = Image.open(out_path).convert("RGBA")

        self.assertEqual(len(turbine_logs), 1)
        self.assertTrue(turbine_logs[0].tower_drawn)
        self.assertGreater(turbine_logs[0].visible_blade_segments, 0)
        self.assertEqual(image.getpixel((10, 100)), (80, 170, 255, 255))
        self.assertEqual(image.getpixel((100, 80)), (0, 255, 120, 255))
        self.assertNotEqual(image.getbbox(), None)

    def test_render_camera_view_scene_preserves_standard_skyline(self) -> None:
        intr = CameraIntrinsics(fx=100.0, fy=100.0, cx=100.0, cy=100.0, width_px=200, height_px=200)
        scene = CameraRenderScene(
            intr=intr,
            pose=CameraPose(
                position=np.zeros(3, dtype=float),
                right=np.array([1.0, 0.0, 0.0], dtype=float),
                up=np.array([0.0, 1.0, 0.0], dtype=float),
                forward=np.array([0.0, 0.0, 1.0], dtype=float),
            ),
            skyline=ProjectedSkyline(
                points=[(0.0, 100.0), (199.0, 100.0)],
                draw_segments=[[(0.0, 100.0), (199.0, 100.0)]],
                x_samples=np.array([0.0, 199.0], dtype=float),
                y_samples=np.array([100.0, 100.0], dtype=float),
                valid_point_count=2,
                x_min=0.0,
                x_max=199.0,
                y_min=100.0,
                y_max=100.0,
            ),
            turbines=[
                ProjectedTurbine(
                    turbine={"id": "WTG01", "base_xyz": [0.0, 0.0, 0.0], "tower_height_m": 100.0, "rotor_diameter_m": 80.0},
                    turbine_id="WTG01",
                    base_point=(100.0, 150.0),
                    hub_point=(100.0, 60.0),
                    hub_depth=1000.0,
                    rotor_radius_px=40.0,
                    in_frame=True,
                )
            ],
            horizon_y=lambda _x: 100.0,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "camera_view.png"
            render_camera_view_scene(out_path, scene, transparent=False, draw_crosshair=False, all_turbine_ids=["WTG01"])
            image = Image.open(out_path).convert("RGBA")

        self.assertEqual(image.getpixel((10, 100)), (80, 170, 255, 255))
        self.assertEqual(image.getpixel((100, 80)), (0, 255, 120, 255))


if __name__ == "__main__":
    unittest.main()
