from functools import cached_property
import logging
from pathlib import Path
import subprocess
from esm.Exceptions import RequirementsNotFulfilledError
from esm.EsmConfigService import EsmConfigService

from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import byteArrayToString, isDebugMode

log = logging.getLogger(__name__)

@Service
class EsmEpmRemoteClientService:
    """
    service that provides easy way to talk with the server

    uses the emp remote client for this.
    """
    @cached_property
    def config(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)

    def checkAndGetEpmRemoteClientPath(self):
        epmRC = self.config.paths.epmremoteclient
        if Path(epmRC).exists():
            return epmRC
        raise RequirementsNotFulfilledError(f"epm remote client not found in the configured path at {epmRC}. Please make sure it exists and the configuration points to it.")

    def sendExit(self, timeout=0):
        """
        sends a "saveandexit $timeout" to the server via the epmremoteclient and returns immediately. 
        You need to check if the server stopped successfully via the other methods
        returns the completed process of the remote client.
        """
        # use the epmremoteclient and send a 'saveandexit x' where x is the timeout in minutes. a 0 will stop it immediately.
        epmrc = self.checkAndGetEpmRemoteClientPath()
        cmd = [epmrc, "run", "-q", f"saveandexit {timeout}"]
        if isDebugMode(self.config):
            cmd = [epmrc, "run", f"saveandexit {timeout}"]
        log.debug(f"executing {cmd}")
        process = subprocess.run(cmd)
        log.debug(f"process returned: {process}")
        # this returns when epmrc ends, not the server!
        if process.returncode > 0:
            stdout = byteArrayToString(process.stdout).strip()
            stderr = byteArrayToString(process.stderr).strip()
            if len(stdout)>0 or len(stderr)>0:
                log.error(f"error executing the epm client: stdout: '{stdout}', stderr: '{stderr}'")
            else:
                log.error(f"error executing the epm client, but no output was provided")
        return process

    def sayOnServer(self, name, message):
        """
        sends a "say 'message'" to the server via the epmremoteclient and returns immediately. 
        returns the completed process of the remote client.

        Unluckily, this is currently only a server message.
        """
        # use the epmremoteclient and send a 'say "message"'
        epmrc = self.checkAndGetEpmRemoteClientPath()
        string = f"say '{name}: {message}'"
        cmd = [epmrc, "run", "-q", string]
        if isDebugMode(self.config):
            cmd = [epmrc, "run", string]
        log.debug(f"executing {cmd}")
        process = subprocess.run(cmd)
        log.debug(f"process returned: {process}")
        # this returns when epmrc ends, not the server!
        if process.returncode > 0:
            if process.stdout and len(process.stdout)>0 and len(process.sterr)>0:
                log.error(f"error executing the epm client: stdout: \n{process.stdout}\n, stderr: \n{process.stderr}\n")
            else:
                log.error(f"error executing the epm client, but no output was provided")
        return process
