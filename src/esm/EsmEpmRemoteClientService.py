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

    its returncodes are:
    None = 0,      
    Unknown = 1,
    ServerConnection = 20,
    RequestError = 21,
    CommandSettings = 30,
    CommandPayload = 31,
    """
    @cached_property
    def config(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)

    def checkAndGetEpmRemoteClientPath(self):
        epmRC = self.config.paths.epmremoteclient
        if Path(epmRC).exists():
            return epmRC
        raise RequirementsNotFulfilledError(f"epm remote client not found in the configured path at {epmRC}. Please make sure it exists and the configuration points to it.")

    def epmrcExecute(self, command, payload, quietMode=True):
        """
            execute epm remote client with given command and string/payload.
        """
        epmrc = self.checkAndGetEpmRemoteClientPath()
        commands = command.split()
        cmdLine = [epmrc] + commands + ["-q", payload]
        if isDebugMode(self.config) or not quietMode:
            cmdLine = [epmrc] + commands + [payload]
        log.debug(f"executing {cmdLine}")
        process = subprocess.run(cmdLine)
        log.debug(f"process returned: {process}")
        # this returns when epmrc ends, not the server!
        if process.returncode > 0:
            stdout = byteArrayToString(process.stdout).strip()
            stderr = byteArrayToString(process.stderr).strip()
            if len(stdout)>0 or len(stderr)>0:
                log.error(f"error executing the epm client: stdout: {stdout}, stderr: {stderr}")
            else:
                log.error(f"error executing the epm client, but no output was provided")
        return process

    def sendExit(self, timeout=0):
        """
        sends a "saveandexit $timeout" to the server via the epmremoteclient and returns immediately. 
        You need to check if the server stopped successfully via the other methods
        returns the completed process of the remote client.
        """
        # use the epmremoteclient and send a 'saveandexit x' where x is the timeout in minutes. a 0 will stop it immediately.
        return self.epmrcExecute(command="run", payload=f"saveandexit {timeout}")
