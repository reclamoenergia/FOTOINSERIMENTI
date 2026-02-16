"""PyInstaller hook to ensure rasterio dynamic modules/data are bundled."""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

hiddenimports = collect_submodules("rasterio")
binaries = collect_dynamic_libs("rasterio")
datas = collect_data_files("rasterio")
