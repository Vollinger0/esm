# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import copy_metadata

datas = [
        ('esm-base-config.yaml', '.'),
        ('esm-custom-config.yaml', '.'),
        ('esm-dedicated.yaml', '.'),
        ('hamster_sync_lines.csv', '.'),
        ('EmpyrionPrime.RemoteClient.Console.exe', '.'),
        ('callesm-async.bat', '.'),
        ('callesm-sync.bat', '.')
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
