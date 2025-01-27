import logging
import subprocess
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import List

from esm.ConfigModels import MainConfig
from esm.exceptions import RequirementsNotFulfilledError
from esm.EsmConfigService import EsmConfigService
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import byteArrayToString

log = logging.getLogger(__name__)

class Priority(Enum):
    ALERT = 0       # red alert with the alert sound, top centered
    WARNING = 1     # yellow warning with the *pling*, top centered
    INFO = 2        # white info box without sound, top centered
    OTHER = 3       # just the plain message in the middle of the screen, probably a bug

class SenderType(Enum):
    Unknown = "Unknown"             #white "??: <msg>"  - probably should not be used 
    Player = "Player"               #white ": <msg>"  - probably should not be used 
    ServerPrio = "ServerPrio"       #red   "SERVER: <msg>"
    ServerInfo = "ServerInfo"       #pink  "SERVER: <msg>"
    ServerForward = "ServerForward" #white ": <msg>" - probably should not be used 
    System = "System"               #green "SYSTEM: <msg>"

class Channel(Enum):
    Global = "Global"               # global channel, just works
    Faction = "Faction"             # needs recipient-id, check emprc help
    Alliance = "Alliance"           # needs recipient-id, check emprc help
    SinglePlayer = "SinglePlayer"   # needs recipient-id, check emprc help
    Server = "Server"               # server channel, doesn't work? - probably should not be used 

class ErrorCodes(Enum):
    NoError = 0
    UnknownError = 1
    ServerConnection = 20
    RequestError = 21
    CommandSettings = 30
    CommandPayload = 31
    Unknown = 99

    @staticmethod
    def byNumber(number):
        for et in list(ErrorCodes):
            if et.value == number:
                return et
        return ErrorCodes.Unknown


@Service
class EsmEmpRemoteClientService:
    """
    service that provides easy way to talk with the server

    uses the emp remote client for this.
    """
    @cached_property
    def config(self) -> MainConfig:
        return ServiceRegistry.get(EsmConfigService).config

    def checkAndGetEmpRemoteClientPath(self) -> Path:
        empRC = Path(self.config.paths.empremoteclient)
        if empRC.exists():
            return empRC
        raise RequirementsNotFulfilledError(f"emp remote client not found in the configured path at {empRC}. Please make sure it exists and the configuration points to it.")

    def emprcExecute(self, commands: List[str], payload=None, quietMode=True, doLog: bool=True) -> subprocess.CompletedProcess:
        """
            execute emp remote client
        """
        emprc = self.checkAndGetEmpRemoteClientPath()
        cmdLine = [emprc.absolute()] + commands
        if quietMode and not self.config.general.debugMode:
            cmdLine = cmdLine + ["-q"]
        if payload != None:
            cmdLine = cmdLine + [payload]
        log.debug(f"calling emp client with: {cmdLine}")
        process = subprocess.run(cmdLine)
        log.debug(f"process returned: {process}")
        # this returns when emprc ends, not the server!
        if process.returncode > 0:
            errorCode = ErrorCodes.byNumber(process.returncode)
            stdout = byteArrayToString(process.stdout).strip()
            stderr = byteArrayToString(process.stderr).strip()
            if doLog:
                if len(stdout)>0 or len(stderr)>0:
                    log.error(f"error {errorCode} executing the emp client: stdout: {stdout}, stderr: {stderr}")
                else:
                    log.error(f"error {errorCode} executing the emp client, but no output was provided")
        return process
    
    def sendServerChat(self, message, quietMode=True) -> subprocess.CompletedProcess:
        """
        sends a "say 'message'" to the server chat via the empremoteclient and returns immediately. 
        returns the completed process of the remote client.

        Unluckily, this is currently only a server message.
        """
        # use the empremoteclient and send a 'say "message"'
        safeMessage = message.replace("'", "").replace('"', '')
        process = self.emprcExecute(["run"], f"say '{safeMessage}'", quietMode, doLog=False)
        if process.returncode > 0:
            log.error(f"Could not send message {message} due to emprc failing with error '{ErrorCodes.byNumber(process.returncode)}'")
        return process
    
    
    def sendAnnouncement(self, message, priority: Priority=Priority.INFO, time: int=5000, quietMode=True) -> subprocess.CompletedProcess:
        """
        announce something on the server, using the provided message and priority and time of the message to stay visible (in ms?)
        This displays the message banner in the top middle of the player view, see the class Priority for details
        """
        # request InGameMessageAllPlayers "{ \"msg\": \"alert from test.bat prio: %%i\", \"prio\": 0, \"time\": 3000 }"
        payload = "{"+f'"msg": "{message}", "prio": {str(priority.value)}, "time": {str(time)}'+"}"
        process = self.emprcExecute(commands=["request", "InGameMessageAllPlayers"], payload=payload, quietMode=quietMode, doLog=False)
        if process.returncode > 0:
            log.error(f"Could not send message {message} due to emprc failing with error '{ErrorCodes.byNumber(process.returncode)}'")
        return process
    
    
    def sendMessage(self, message, senderName=None, quietMode=True, channel: Channel=Channel.Global, senderType: SenderType=SenderType.ServerInfo):
        """
            sends a message to the server, usually global chat
            when senderName is set, sender-type becomes irrelevant
            senderName and message can contain bb-code for coloring, e.g. "[783456]so[345678]many[567834]colors"

          - message --sender-name "SenderNameOverride" --channel SinglePlayer --sender-type ServerInfo "Hello World!"
        """
        commands = ["message"]
        if senderName:
            commands = commands + ["--sender-name", senderName]
        if senderType:
            commands = commands + ["--sender-type", senderType.value]
        if channel:
            commands = commands + ["--channel", channel.value]
        commands = commands + [message]
        process = self.emprcExecute(commands=commands, quietMode=quietMode, doLog=False)
        if process.returncode > 0:
            log.error(f"Could not send message '{message}' due to emprc failing with error '{ErrorCodes.byNumber(process.returncode)}'")
        return process

    def sendExit(self, timeout=0) -> subprocess.CompletedProcess:
        """
        sends a "saveandexit $timeout" to the server via the empremoteclient and returns immediately. 
        You need to check if the server stopped successfully via the other methods
        returns the completed process of the remote client.
        """
        # use the empremoteclient and send a 'saveandexit x' where x is the timeout in minutes. a 0 will stop it immediately.
        return self.emprcExecute(commands=["run"], payload=f"saveandexit {timeout}")
