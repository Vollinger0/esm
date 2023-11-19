# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import shutil
from PyInstaller.utils.hooks import copy_metadata

# all entries with dst == "." will end up next to the exe (see fix below)
datas = [
        ('esm-base-config.yaml', '.'),
        ('esm-custom-config.yaml', '.'),
        ('esm-dedicated.yaml', '.'),
        ('hamster_sync_lines.csv', '.'),
        ('emprc/EmpyrionPrime.RemoteClient.Console.exe', './emprc'),
        ('callesm-async.bat', '.'),
        ('callesm-sync.bat', '.'),
        ('readme.md', '.'),
        ('install.md', '.'),        
        ('backups.md', '.'),        
        ('performance.md', '.'),
        ('development.md', '.'),
        ]
datas += copy_metadata('esm')

a = Analysis(
    ['wrapper.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    metadatas=['esm']
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='esm',
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
    icon=['anvil_hamster_mirrored.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='esm',
)

# fix the location of the collected extra files that we want to have next to the .exe, not in _internal.
print(f"working directory is: {Path(".").resolve()}")
srcDir = Path(f"./dist/esm/_internal/").resolve()
dstDir = Path(f"{srcDir.parent}")
for src, dst in datas:
    if dst[0]==".":
        print(f"processing datas entry {src, dst}") 
        # move the file up one directory
        srcPath = Path(f"{srcDir}/{src}")
        dstPath = Path(f"{dstDir}/{src}")
        print(f"moving {srcPath} -> {dstPath}")
        if not Path(dstPath.parent).exists(): Path(dstPath.parent).mkdir(parents=True, exist_ok=True)
        shutil.move(srcPath, dstPath)