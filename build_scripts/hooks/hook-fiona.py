"""PyInstaller hook to bundle Fiona modules, binaries and data files."""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

hiddenimports = collect_submodules("fiona")
binaries = collect_dynamic_libs("fiona")
datas = collect_data_files("fiona")
