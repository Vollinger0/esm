from functools import cached_property
import logging
from pathlib import Path
import subprocess
from esm.ConfigModels import MainConfig
from esm.EsmConfigService import EsmConfigService
from esm.EsmFileSystem import EsmFileSystem
from esm.exceptions import RequirementsNotFulfilledError
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import getElapsedTime, getTimer

log = logging.getLogger(__name__)

@Service
class EsmSteamService:

    @cached_property
    def config(self) -> MainConfig:
        return ServiceRegistry.get(EsmConfigService).config
    
    @cached_property
    def fileSystem(self) -> EsmFileSystem:
        return ServiceRegistry.get(EsmFileSystem)

    def installGame(self):
        """
        calls steam to install the game via steam to the given installation directory

        $ %steamCmdPath% +force_install_dir %installPath% +login anonymous +app_update 530870 validate +quit"
        """
        # steam install
        steamcmdExe = self.checkAndGetSteamCmdExecutable()
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
    
    def updateGame(self, steam=True, additionals=True):
        """
        calls steam to update the game via steam and call any additionally configured steps (like updating the scenario, copying files etc.)

        # %steamCmdPath% +force_install_dir %installPath% +login anonymous +app_update 530870 validate +quit"
        """
        # steam update is actually the exact same call as the install command, so we'll call just that instead.
        if steam:
            self.installGame()

        if additionals:
            # additional copying according to configuration
            self.fileSystem.copyAdditionalUpdateStuff()
        
        if not steam and not additionals:
            log.warning("Well nothing to do here. You need to omit at least one of the options '--nosteam' or '--noadditionals'.")

    def checkAndGetSteamCmdExecutable(self):
        """
        checks that the steam executable exists and returns its path.
        """
        steamcmdExe = self.config.paths.steamcmd
        if Path(steamcmdExe).exists():
            return steamcmdExe
        raise RequirementsNotFulfilledError(f"steamcmd.exe not found in the configured path at {steamcmdExe}. Please make sure it exists and the configuration points to it.")
