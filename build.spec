# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH)
analysis = Analysis(
    [str(root / "src" / "main.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    excludes=[],
)
pyz = PYZ(analysis.pure)

# Qt's unversioned ICU imports and the UCRT resolve against Windows itself.
# A build machine can have incompatible copies on PATH.
system_libraries = {"icu.dll", "icuuc.dll", "icuin.dll", "ucrtbase.dll"}
windows_binaries = [
    (name, source, kind)
    for name, source, kind in analysis.binaries
    if Path(name).name.lower() not in system_libraries
    and not Path(name).name.lower().startswith(("api-ms-win-", "ext-ms-win-", "icudt"))
]

EXE(
    pyz,
    analysis.scripts,
    windows_binaries,
    analysis.datas,
    [],
    name="CS2-Sensitivity-Generator",
    console=False,
    upx=False,
    manifest=str(root / "scripts" / "windows.manifest"),
)
