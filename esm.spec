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
        ('EmpyrionPrime.RemoteClient.Console.exe', '.'),
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='wrapper',
)


# fix the location of the collected extra files that we want to have next to the exe, not in _internal.
print(f"working directory is: {Path(".").resolve()}")
for src, dst in datas:
    if dst == ".":
        print(f"processing datas entry {src, dst}") 
        # move the file up one directory
        srcDir = Path(f"./dist/wrapper/_internal/").resolve()
        srcPath = Path(f"{srcDir}/{src}")
        dstDir = Path(f"{srcDir.parent}")
        print(f"moving {srcPath} -> {dstDir}")
        shutil.move(srcPath, dstDir)