from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import rasterio
from rasterio.windows import Window


@dataclass
class SampleResult:
    value: Optional[float]
    is_nodata: bool


class DTM:
    """Simple GeoTIFF sampler used for horizon computation."""

    def __init__(self, geotiff_path: str | Path) -> None:
        self.path = str(geotiff_path)
        self.ds = rasterio.open(self.path)
        self.nodata = self.ds.nodata
        self.transform = self.ds.transform
        self.width = self.ds.width
        self.height = self.ds.height

        px = abs(float(self.transform.a))
        py = abs(float(self.transform.e))
        self.pixel_size = (px + py) / 2.0

    def close(self) -> None:
        self.ds.close()

    def __enter__(self) -> "DTM":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _is_nodata(self, value: float) -> bool:
        if np.isnan(value):
            return True
        if self.nodata is None:
            return False
        return bool(np.isclose(value, self.nodata))

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
