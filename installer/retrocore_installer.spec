# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path.cwd()
payload_zip = project_root / "installer" / "payload" / "retrocore-package.zip"

a = Analysis(
    [str(project_root / "installer" / "retrocore_installer.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[(str(payload_zip), ".")],
    hiddenimports=["tkinter"],
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
    a.binaries,
    a.datas,
    [],
    name="retrocore-installer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "branding" / "retrocore.ico"),
    uac_admin=True,
)
