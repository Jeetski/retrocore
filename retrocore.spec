# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path.cwd()
datas = [
    (str(project_root / "branding"), "branding"),
    (str(project_root / "docs"), "docs"),
    (str(project_root / "shaders"), "shaders"),
    (str(project_root / "HELP.md"), "."),
    (str(project_root / "LICENSE"), "."),
    (str(project_root / "README.md"), "."),
    (str(project_root / "ALPHA-LAUNCH.md"), "."),
    (str(project_root / "retrocore.json"), "."),
    (str(project_root / "presets.json"), "."),
]


a = Analysis(
    ["retrocore.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=["PIL._tkinter_finder"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="retrocore",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "branding" / "retrocore.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="retrocore",
)
