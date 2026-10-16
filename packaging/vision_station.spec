# PyInstaller spec (TD-15): one folder, console program. Build from the repository root:
#   uv run --group build pyinstaller packaging/vision_station.spec --noconfirm
# Needs frontend/dist (npm run build) and, optionally, packaging/build_info.json and THIRD_PARTY_LICENSES.md.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

root = Path(SPECPATH).parent  # noqa: F821 (set by PyInstaller)
web = root / "frontend" / "dist"
if not (web / "index.html").is_file():
    raise SystemExit("frontend/dist is missing: run `cd frontend && npm ci && npm run build` first")

datas = [(str(web), "web")]
for extra in ("packaging/build_info.json", "THIRD_PARTY_LICENSES.md"):
    if (root / extra).is_file():
        datas.append((str(root / extra), "."))
datas += collect_data_files("onnxruntime")

binaries = collect_dynamic_libs("zxingcpp") + collect_dynamic_libs("onnxruntime")

hidden = (
    collect_submodules("vision_station")
    + collect_submodules("uvicorn")
    + ["zxingcpp", "onnxruntime", "yaml", "multipart"]
)
try:  # the C920 controls (Windows only, optional extra "uvc")
    import duvc_ctl  # noqa: F401

    hidden.append("duvc_ctl")
    binaries += collect_dynamic_libs("duvc_ctl")
except ImportError:
    pass

a = Analysis(  # noqa: F821
    [str(root / "packaging" / "entry.py")],
    pathex=[str(root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "onnx"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="vision-station",
    console=True,
    icon=str(root / "packaging" / "icon.ico") if (root / "packaging" / "icon.ico").is_file() else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="vision-station")  # noqa: F821
