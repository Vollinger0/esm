# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import shutil
import subprocess
from PyInstaller.utils.hooks import copy_metadata
from esm import __main__ as info
from esm.EsmConfigService import EsmConfigService

version = info.getPackageVersion()
print(f"esm version: {version}")

# install the esm module so dist will pick up the current state
subprocess.run("pip install -e .", shell=True)

# create a new default config file
EsmConfigService.createDefaultConfigFile()

print ("Proceeding with pyinstaller spec")
# define the files to copy to the dist additionally
datafiles = [
        ('esm-default-config.example.yaml', '.'),
        ('esm-custom-config.example.yaml', '.'),
        ('esm-dedicated.example.yaml', '.'),
        ('hamster_sync_lines.csv', '.'),
        ('emprc/EmpyrionPrime.RemoteClient.Console.exe', 'emprc/EmpyrionPrime.RemoteClient.Console.exe'),
        ('callesm-async.example.bat', '.'),
        ('callesm-sync.example.bat', '.'),
        ('esm-starter-for-eah.example.cmd', '.'),
        ('readme.md', '.'),
        ('readme_install.md', '.'),        
        ('readme_backups.md', '.'),        
        ('readme_performance.md', '.'),
        ('readme_development.md', '.'),
        ('readme_shareddata.md', '.'),
        ('index.template.html', '.'),
        ('wwwroot/styles.css', 'wwwroot/styles.css'),
        ('wwwroot/favicon.ico', 'wwwroot/favicon.ico'),
        ('wwwroot/chatlog/index.html', 'wwwroot/chatlog/index.html'),
        ('wwwroot/chatlog/script.js', 'wwwroot/chatlog/script.js'),
        ('wwwroot/chatlog/styles.css', 'wwwroot/chatlog/styles.css'),
        ]

a = Analysis(
    ['src/esm/__main__.py'],
    pathex=[],
    binaries=[],
    datas=copy_metadata('esm'),
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

print("Manually copying datafiles to distfolder")
# since the datafile-functinality of pyinstaller is sub-optimal, lets copy our datafiles to the dist folder ourselves.
workspaceDir = Path(".").resolve()
print(f"working directory is: {workspaceDir}")
targetDir = workspaceDir.joinpath("dist/esm")
if not targetDir.exists(): targetDir.mkdir(exist_ok=True)
for src, dst in datafiles:
    print(f"processing datafiles entry {src, dst}") 
    srcPath = workspaceDir.joinpath(src)
    dstPath = targetDir.joinpath(dst)
    print(f"copying {srcPath} -> {dstPath}")
    if not Path(dstPath.parent).exists(): Path(dstPath.parent).mkdir(parents=True, exist_ok=True)
    shutil.copy(srcPath, dstPath)

print("Zipping distribution")
# create a zip file of the distribution in the dist folder, ready do share
sourcePath = targetDir
backupDir = targetDir.parent
version = info.getPackageVersion()
zipFilename = backupDir.joinpath(f"esm-{version}")
archived = shutil.make_archive(zipFilename, 'zip', sourcePath)
print(f"zipped distribution as: {archived}")