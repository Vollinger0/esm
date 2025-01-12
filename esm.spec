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
        ('data/esm-default-config.example.yaml', None),
        ('data/esm-custom-config.example.yaml', None),
        ('data/esm-dedicated.example.yaml', None),
        ('data/hamster_sync_lines.csv', None),
        ('emprc/EmpyrionPrime.RemoteClient.Console.exe', None),
        ('data/callesm-async.example.bat', None),
        ('data/callesm-sync.example.bat', None),
        ('data/esm-taskprocessor.example.bat', None),
        ('data/esm-starter-for-eah.example.cmd', None),
        ('readme.md', None),
        ('data/readme_install.md', None),
        ('data/readme_backups.md', None),
        ('data/readme_performance.md', None),
        ('data/readme_development.md', None),
        ('data/readme_shareddata.md', None),
        ('data/index.template.html', None),
        ('data/index.shared.template.html', None),
        ('wwwroot/styles.css', None),
        ('wwwroot/favicon.ico', None),
        ('wwwroot/chatlog/index.html', None),
        ('wwwroot/chatlog/script.js', None),
        ('wwwroot/chatlog/styles.css', None),
        ]

def copyDataFiles():
    # since the datafile-functionality of pyinstaller is sub-optimal, lets copy our datafiles to the dist folder ourselves.
    print("Manually copying datafiles to distfolder")
    workspaceDir = Path(".").resolve()
    print(f"working directory is: {workspaceDir}")
    targetDir = workspaceDir.joinpath("dist/esm")
    if not targetDir.exists(): targetDir.mkdir(exist_ok=True)
    for src, dst in datafiles:
        if dst is None: dst = src
        print(f"processing datafiles entry {src, dst}") 
        srcPath = workspaceDir.joinpath(src)
        dstPath = targetDir.joinpath(dst)
        print(f"copying {srcPath} -> {dstPath}")
        if not Path(dstPath.parent).exists(): Path(dstPath.parent).mkdir(parents=True, exist_ok=True)
        shutil.copy(srcPath, dstPath)

def zipDistribution():
    workspaceDir = Path(".").resolve()
    print(f"working directory is: {workspaceDir}")
    targetDir = workspaceDir.joinpath("dist/esm")
    print("Zipping distribution")
    # create a zip file of the distribution in the dist folder, ready do share
    sourcePath = targetDir
    backupDir = targetDir.parent
    version = info.getPackageVersion()
    zipFilename = backupDir.joinpath(f"esm-{version}")
    archived = shutil.make_archive(zipFilename, 'zip', sourcePath)
    print(f"zipped distribution as: {archived}")

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
    icon=['data/anvil_hamster_mirrored.ico'],
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

copyDataFiles()
zipDistribution()
