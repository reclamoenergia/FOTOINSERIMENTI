from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import rasterio
from rasterio.windows import Window


@dataclass
class SampleResult:
    value: Optional[float]
    is_nodata: bool


class DTMSampler:
    """Sample elevation values from a GeoTIFF DTM/DEM."""

    def __init__(self, geotiff_path: str | Path) -> None:
        self.path = str(geotiff_path)
        self.ds = rasterio.open(self.path)
        self.nodata = self.ds.nodata
        self.width = self.ds.width
        self.height = self.ds.height
        self.transform = self.ds.transform

        self.pixel_size_x = abs(float(self.transform.a))
        self.pixel_size_y = abs(float(self.transform.e))
        self.pixel_size = float((self.pixel_size_x + self.pixel_size_y) / 2.0)

    def close(self) -> None:
        self.ds.close()

    def __enter__(self) -> "DTMSampler":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _is_nodata(self, value: float) -> bool:
        if np.isnan(value):
            return True
        if self.nodata is None:
            return False
        return np.isclose(value, self.nodata)

    def sample_nearest(self, x: float, y: float) -> SampleResult:
        col_f, row_f = ~self.transform * (x, y)
        col = int(round(col_f))
        row = int(round(row_f))

        if col < 0 or row < 0 or col >= self.width or row >= self.height:
            return SampleResult(value=None, is_nodata=True)

        value = float(self.ds.read(1, window=Window(col, row, 1, 1))[0, 0])
        if self._is_nodata(value):
            return SampleResult(value=None, is_nodata=True)
        return SampleResult(value=value, is_nodata=False)

    def sample_bilinear(self, x: float, y: float) -> SampleResult:
        col_f, row_f = ~self.transform * (x, y)

        c0 = int(np.floor(col_f))
        r0 = int(np.floor(row_f))
        c1 = c0 + 1
        r1 = r0 + 1

        if c0 < 0 or r0 < 0 or c1 >= self.width or r1 >= self.height:
            return self.sample_nearest(x, y)

        window = Window(c0, r0, 2, 2)
        block = self.ds.read(1, window=window)

        z00 = float(block[0, 0])
        z10 = float(block[0, 1])
        z01 = float(block[1, 0])
        z11 = float(block[1, 1])

        if any(self._is_nodata(v) for v in (z00, z10, z01, z11)):
            return self.sample_nearest(x, y)

        tx = col_f - c0
        ty = row_f - r0

        z0 = z00 * (1.0 - tx) + z10 * tx
        z1 = z01 * (1.0 - tx) + z11 * tx
        z = z0 * (1.0 - ty) + z1 * ty
        return SampleResult(value=float(z), is_nodata=False)
