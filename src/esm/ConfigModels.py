from enum import Enum
from pathlib import Path
from typing import List, Optional, TypedDict
from pydantic import BaseModel, Field
from easyconfig import AppConfigMixin, AppBaseModel

FILESIZEPATTERN = r"^\d+(\.\d+)?\s*[KkMmGgTtPpEeZzYy]$"

"""
- if a field is required, set the default value to "...", its parent class then has to be "..." in the main config too.
"""

class ConfigGeneral(BaseModel):
    useRamdisk: bool = Field(True, description="if True, use a ramdisk for the savegame. Requires the user to call ramdisk-install and ramdisk-setup to work. Will completely solve your server performance issues.")
    externalizeTemplates: bool = Field(True, description="if True, will 'externalize' the savegame templates, meaning that they will be symlinked back to the hdd when using the ramdisk. This saves aboit 40% of space on the ramdisk!")
    bindingPort: int = Field(6969, lt=65535, gt=1024, description="default port to bind this application to, just used to make sure only one instance can run with one config at a time.")
    multipleInstanceWaitInterval: int = Field(10, description="interval in seconds for checking if there is another script running at script start")
    multipleInstanceWaitTries: int = Field(180, description="amount of times of checking if there is another script running at script start")
    debugMode: bool = Field(False, description="if True, most file system operations will not be executed and processes not started. You probably don't need this unless you're developing this.")

class StartMode(str, Enum):
    """
    The start mode defines if eleon's launcher is used or not to start the game. If you use the launcher, you can NOT have multiple instances of the game on the same machine. 
    """
    DIRECT = "direct" # will bypass the launcher and use the dedicated exe directly. Use this mode if you need to run multiple instances of the server on one machine.
    LAUNCHER = "launcher" # will use the launcher to start the game

class ConfigServer(BaseModel):
    dedicatedYaml: Path = Field(..., description="name of the dedicated yaml, make sure this is the one defined in EAH if you use that")
    startMode: StartMode = Field(StartMode.LAUNCHER, description="use 'launcher' if you want to start the game the usual way. The launcher itself will then start the dedicated server. Use 'direct' if you want to bypass the launcher, e.g. if you want to run multiple instances of the server on the same machine.")
    gfxMode: bool = Field(False, description="If True, enables the blue graphics overlay of the server, probably not needed when you use EAH or something else to manage the server. This uses the '-startDediWithGfx' param in the launcher - which enables the server graphics overlay, you may want to use this when you have no other means of stopping the server")
    minDiskSpaceForStartup: str = Field("2G", pattern=FILESIZEPATTERN, description="if disk space on the drive with the savegame (or ramdisk) is below this, do NOT start the server to avoid savegame corruption. gnu notation")
    startUpSleepTime: int = Field(20, description="min amount of time in seconds to wait for the server to start up when creating a new savegame")
    launcherMaxStartupTimeout: int = Field(15, description="max amount of time in seconds to find the dedicated exe after calling the launcher")
    sendExitTimeout: int = Field(60, description="amount of seconds to wait until we give up stopping the server and throw an error")
    sendExitInterval: int = Field(5, description="how many seconds to wait before retrying to send another 'saveandexit' to the server to stop it")

class ConfigRamdisk(BaseModel):
    drive: str = Field("R:", pattern=r"[A-Z]\:", description="the drive letter to use for the ramdisk, e.g. 'R:'")
    size: str = Field("2G", pattern=FILESIZEPATTERN, description="ramdisk size to use, e.g. '5G' or '32G', etc. If you change this, the ramdisk needs to be re-mounted, and the setup needs to run again.")
    synchronizeRamToMirrorInterval: int = Field(3600, description="interval in seconds at which to do a ram2hdd sync for the savegame. if interval=0 the sync will be disabled! Recommended to leave at 3600 (1h)")

class ConfigBackups(BaseModel):
    amount: int = Field(4, description="amount of rolling mirror backups to keep")
    marker: str = Field("esm_this_is_the_latest_backup", description="filename used for the marker that marks as backup as being the latest")
    staticBackupPeaZipOptions: str = Field("a -tzip -mtp=0 -mm=Deflate64 -mmt=on -mx1 -mfb=32 -mpass=1 -sccUTF-8 -mcu=on -mem=AES256 -bb0 -bse0 -bsp2", description="make sure to use the fastest compression options")
    minDiskSpaceForStaticBackup: str = Field("2G", pattern=FILESIZEPATTERN, description="if disk space on the drive with the backups has less free space than this, do not create a backup. gnu notation")
    additionalBackupPaths: List[Path] = Field([], description="list of full paths to source files or directories to backup additionally. Those will all end up in the folder 'Additional' in the backup")

class FileOps(BaseModel):
    """ represents a file operation for the update-command with file path patterns for src and dst """
    src: str
    dst: str

class ConfigUpdates(BaseModel):
    scenariosource: Path = Field("D:/Servers/Scenarios", description="source directory with the scenario folders that will be used to copy to the servers scenario folder")
    additional: List[FileOps] = Field([], description="additional stuff to copy when calling the esm game-update command, every line has to look like e.g. { src: 'foo', dst: 'bar' }")

class ConfigDeletes(BaseModel):
    """
    Configure which logs to back up when using the 'deleteall' command
    You can also configure additional paths of stuff to delete
    """
    backupGameLogs: bool = Field(True, description="backup all game logs on deleteall command")
    backupEahLogs: bool = Field(True, description="backup all eah logs on deleteall command?")
    backupEsmLogs: bool = Field(True, description="backup all esm logs on deleteall command?")
    additionalDeletes: List[Path] = Field([], description="additional paths of stuff to delete when using the 'deleteall' command")

class ConfigPaths(BaseModel):
    install: Path = Field(..., description="the games main installation location")
    osfmount: Path = Field("D:/Servers/Tools/OSFMount/osfmount.com", description="path to osfmount executable needed to mount the ram drive")
    peazip: Path = Field("D:/Servers/Tools/PeaZip/res/bin/7z/7z.exe", description="path to peazip used for the static backups")
    epmremoteclient: Path = Field("D:/Servers/Tools/esm/emprc/EmpyrionPrime.RemoteClient.Console.exe", description="path to emprc, used to send commands to the server")
    eah: Path = Field("D:/Servers/Empyrion/DedicatedServer/EmpyrionAdminHelper", description="path to EAH, for backing up its data")
    steamcmd: Path = Field("D:/Servers/Tools/steamcmd/steamcmd.exe", description="path to steamcmd for installs and updates of the game server")

class ConfigFoldernames(BaseModel):
    games: str = Field("Games")
    backup: str = Field("Backup")
    playfields: str = Field("Playfields")
    templates: str = Field("Templates")
    shared: str = Field("Shared")
    backupmirrors: str = Field("BackupMirrors")
    backupmirrorprefix: str = Field("rollingBackup_")
    dedicatedserver: str = Field("DedicatedServer")
    gamesmirror: str = Field("GamesMirror")
    savegamemirrorpostfix: str = Field("_Mirror")
    savegametemplatepostfix: str = Field("_Templates")
    esmtests: str = Field("esm-tests", description="this folder will be used to conduct a few tests on the filesystem below the installation dir")

class ConfigFilenames(BaseModel):
    globaldb: str = Field("global.db")
    buildNumber: str = Field("BuildNumber.txt")
    dedicatedExe: str = Field("EmpyrionDedicated.exe")
    launcherExe: str = Field("EmpyrionLauncher.exe")

class ConfigCommunication(BaseModel):
    announceSyncEvents: bool = Field(True, description="if true, sync events (syncStart, syncEnd) will be announced in the chat")
    announceSyncProbability: float = Field(0.3, ge=0, le=1, description="probability factor that a sync will be announced at all, this is to avoid it being too spammy. something between 0.0 and 1.0")
    synceventname: str = Field("[0fa336]Hamster-News", description="the name to be used when announcing a sync on the server, may contain bb-code for colors and such")
    synceventmessageprefix: str = Field("[aaaaaa]", description="this string will be prepended to all sync event messages, you can use this to set a bb-color code")
    synceventsfile: str = Field("hamster_sync_lines.csv", description="should contain the path to a csv file with two columns, each containing the first and second sentence. The first will be used when starting a sync, the second when its finished.")

class RobocopyOptions(BaseModel):
    moveoptions: str = Field("/MOVE /E /np /ns /nc /nfl /ndl /mt /r:10 /w:10 /unicode", alias="move")
    copyoptions: str = Field("/MIR  /np /ns /nc /nfl /ndl /mt /r:10 /w:10 /unicode", alias="copy")

class ConfigRobocopy(BaseModel):
    encoding: str = Field("ansi", description="depending on the shell used, it may be necessary to change this to ansi, utf-8, cp1252 or something. This will be passed to subprocess.run(...encoding=...)")
    options: RobocopyOptions = Field(RobocopyOptions(), description="options for the different robocopy operations")

class ConfigGalaxy(BaseModel):
    territories: Optional[List[dict]] = None

class DediServerConfig(BaseModel):
    """represents the serverconfig fragment of the dedicated yaml"""
    AdminConfigFile: Optional[str] = None
    SaveDirectory: Optional[str] = None
    Srv_Name: Optional[str] = None
    Srv_Description: Optional[str] = None
    Srv_Password: Optional[str] = None
    Srv_MaxPlayers: Optional[int] = None
    Srv_Port: Optional[int] = None
    MaxAllowedSizeClass: Optional[int] = None
    PlayerLoginParallelCount: Optional[int] = None
    PlayerLoginFullServerQueueCount: Optional[int] = None

class DediGameConfig(BaseModel):
    """represents the gameconfig fragment of the dedicated yaml"""
    GameName: Optional[str] = None
    CustomScenario: Optional[str] = None
    SharedDataURL: Optional[str] = None

class DediConfig(BaseModel):
    """represents the dedicated yaml"""
    ServerConfig: Optional[DediServerConfig] = None
    GameConfig: Optional[DediGameConfig] = None

class DownloadToolConfig(BaseModel):
    """represents the download tool config"""
    serverPort: int = Field(27440, description="port of the webserver to listen to. Make sure this port is reachable from outside")
    maxGlobalBandwith: int = Field(50*1000*1000, description="max bandwith to use for the downloads globally in bytes, e.g. 50 MB/s")
    maxClientBandwith: int = Field(30*1000*1000, description="max bandwith to use for the download per client in bytes, e.g. 30 MB/s")
    rateLimit: str = Field("10 per minute", description="rate limit of max allowed requests per ip address per time unit, e.g. '10 per minute' or '10 per hour'")

    useSharedDataURLFeature: bool = Field(False, description="if true, a zip for the SharedDataURL feature will be created, served and the dedicated yaml will be automatically edited.")
    autoZipName: str = Field("SharedData.zip", description="The filename of the zip file for the auto download of the SharedDataURL feature postfixed with _yyyymmdd_hhmmss so the client recognizes this as a new file on recreation.")

    useCustomCacheFolderName: bool = Field(False, description="if true, the custom folder name will be used, if false, the folder name will be generated with following pattern '{gamename}_{serverip}_{uniquegameid}'")
    customCacheFolderName: str = Field("DediGame_127.0.0.1_123456789", description="name of the folder included in the zip file, which will look something like 'DediGame_127.0.0.1_12346789', depending on gamename, server ip and unique game id")
    manualZipName: str = Field("shareddata_copy_to_empyrion_saves_cache.zip", description="The filename of the zip file that will be provided as manual download")

    timeToAddToModificationTimestamps: int = Field(43200, description="how much time should be added to the modification timestamps of the files in the cache folder, so the game recognizes them as up to date. Should be 12 hours (default) or more.")
    wwwroot: str = Field("wwwroot", description="folder to use as wwwroot, where the download will be served from")
    tempFolder: str = Field("temp", description="temporary folder for creating the downloadable zip")

class MainConfig(AppBaseModel, AppConfigMixin):
    general: ConfigGeneral = Field(ConfigGeneral())
    server: ConfigServer = Field(...)
    ramdisk: ConfigRamdisk = Field(ConfigRamdisk())
    backups: ConfigBackups = Field(ConfigBackups())
    updates: ConfigUpdates = Field(ConfigUpdates())
    deletes: ConfigDeletes = Field(ConfigDeletes())
    paths: ConfigPaths = Field(...)
    foldernames: ConfigFoldernames = Field(ConfigFoldernames(), description="names of different folders, you probably do not need to change any of these")
    filenames: ConfigFilenames = Field(ConfigFilenames(), description="names of different files, you probably do not need to change any of these")
    communication: ConfigCommunication = Field(ConfigCommunication(), description="configuration for the in-game communication")
    robocopy: ConfigRobocopy = Field(ConfigRobocopy())
    galaxy: Optional[ConfigGalaxy] = None
    dedicatedConfig: Optional[DediConfig] = Field(None)
    context: Optional[dict] = {}
    downloadtool: DownloadToolConfig = Field(DownloadToolConfig(), description="configuration for the shared data download tool")
