from functools import cached_property
import logging
from pathlib import Path
import subprocess
from esm.Exceptions import RequirementsNotFulfilledError
from esm.EsmConfigService import EsmConfigService
from esm.FsTools import FsTools
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import getElapsedTime, getTimer

log = logging.getLogger(__name__)

@Service
class EsmSteamService:

    @cached_property
    def config(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)

    def installGame(self):
        """
        calls steam to install the game via steam to the given installation directory

        $ %steamCmdPath% +force_install_dir %installPath% +login anonymous +app_update 530870 validate +quit"
        """
        # steam install
        steamcmdExe = self.getSteamCmdExecutable()
        installPath = self.config.paths.install
        cmd = [steamcmdExe]
        cmd.extend(str(f"+force_install_dir {installPath} +login anonymous +app_update 530870 validate +quit").split(" "))
        log.debug(f"executing {cmd}")
        start = getTimer()
        process = subprocess.run(cmd)
        elapsedTime = getElapsedTime(start)
        log.debug(f"after {elapsedTime} process returned: {process} ")
        # this returns when the process finishes
        if process.returncode > 0:
            log.error(f"error executing steamcmd: stdout: \n{process.stdout}\n, stderr: \n{process.stderr}\n")
    
    def updateGame(self, nosteam=False):
        """
        calls steam to update the game via steam and call any additionally configured steps (like updating the scenario, copying files etc.)

        # %steamCmdPath% +force_install_dir %installPath% +login anonymous +app_update 530870 validate +quit"
        """
        # steam update is actually the exact same call as the install command, so we'll call just that instead.
        if not nosteam:
            self.installGame()

        # additional copying according to configuration
        self.copyAdditionalUpdateStuff()

    def getSteamCmdExecutable(self):
        """
        checks that the steam executable exists and returns its path.
        """
        steamcmdExe = self.config.paths.steamcmd
        if Path(steamcmdExe).exists():
            return steamcmdExe
        raise RequirementsNotFulfilledError(f"steamcmd.exe not found in the configured path at {steamcmdExe}. Please make sure it exists and the configuration points to it.")
    
    def copyAdditionalUpdateStuff(self):
        """
        copies any additionally configured stuff in the config under updates.additional
        """
        additionalStuffList = self.config.updates.additional
        if additionalStuffList is None or len(additionalStuffList) <= 0:
            return
        
        copiedFiles = 0
        copiedDirs = 0
        
        for additionalStuff in additionalStuffList:
            sourcePath = Path(additionalStuff.src)
            if not Path(sourcePath).is_absolute():
                sourcePath = Path(f"{self.config.paths.install}/{sourcePath}")
            
            destinationPath = Path(additionalStuff.dst)
            if not Path(destinationPath).is_absolute():
                destinationPath = Path(f"{self.config.paths.install}/{destinationPath}")

            log.info(f"copying {sourcePath} to {destinationPath}")
            
            sourcePaths = FsTools.resolveGlobs([sourcePath])
            for source in sourcePaths:
                if source.exists():
                    if source.is_dir():
                        # its a dir
                        log.debug(f"copying directory {source} into {destinationPath}")  
                        FsTools.copyDir(source=source, destination=destinationPath)
                        copiedDirs += 1
                    else:
                        # its a file
                        log.debug(f"copying file {source} into {destinationPath}")  
                        FsTools.copy(source=source, destination=destinationPath)
                        copiedFiles += 1
                else:
                    log.warning(f"Configured additional path {source} does not exist.")
        log.info(f"Copied {copiedDirs} folders and {copiedFiles} files.")
