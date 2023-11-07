from enum import Enum
from functools import cached_property
import logging
from pathlib import Path
import subprocess
from typing import List
from esm.Exceptions import RequirementsNotFulfilledError
from esm.EsmConfigService import EsmConfigService

from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import byteArrayToString, isDebugMode

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
    Faction = "Faction"             # needs recipient-id, check epmrc help
    Alliance = "Alliance"           # needs recipient-id, check epmrc help
    SinglePlayer = "SinglePlayer"   # needs recipient-id, check epmrc help
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

    def epmrcExecute(self, commands: [str], payload=None, quietMode=True):
        """
            execute epm remote client
        """
        epmrc = self.checkAndGetEpmRemoteClientPath()
        cmdLine = [epmrc] + commands
        if quietMode and not isDebugMode(self.config):
            cmdLine = cmdLine + ["-q"]
        if payload != None:
            cmdLine = cmdLine + [payload]
        log.debug(f"calling epm client with: {cmdLine}")
        process = subprocess.run(cmdLine)
        log.debug(f"process returned: {process}")
        # this returns when epmrc ends, not the server!
        if process.returncode > 0:
            errorCode = ErrorCodes.byNumber(process.returncode)
            stdout = byteArrayToString(process.stdout).strip()
            stderr = byteArrayToString(process.stderr).strip()
            if len(stdout)>0 or len(stderr)>0:
                log.error(f"error {errorCode} executing the epm client: stdout: {stdout}, stderr: {stderr}")
            else:
                log.error(f"error {errorCode} executing the epm client, but no output was provided")
        return process
    
    def sendServerChat(self, message, quietMode=True):
        """
        sends a "say 'message'" to the server chat via the epmremoteclient and returns immediately. 
        returns the completed process of the remote client.4

        Unluckily, this is currently only a server message.
        """
        # use the epmremoteclient and send a 'say "message"'
        return self.epmrcExecute(["run"], f"say '{message}'", quietMode)
    
    def sendAnnouncement(self, message, priority: Priority=Priority.INFO, time: int=5000, quietMode=True):
        """
        announce something on the server, using the provided message and priority and time of the message to stay visible (in ms?)
        This displays the message banner in the top middle of the player view, see the class Priority for details
        """
        # request InGameMessageAllPlayers "{ \"msg\": \"alert from test.bat prio: %%i\", \"prio\": 0, \"time\": 3000 }"
        payload = "{"+f'"msg": "{message}", "prio": {str(priority.value)}, "time": {str(time)}'+"}"
        return self.epmrcExecute(commands=["request", "InGameMessageAllPlayers"], payload=payload, quietMode=quietMode)
    
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
        return self.epmrcExecute(commands=commands, quietMode=quietMode)

    def sendExit(self, timeout=0):
        """
        sends a "saveandexit $timeout" to the server via the epmremoteclient and returns immediately. 
        You need to check if the server stopped successfully via the other methods
        returns the completed process of the remote client.
        """
        # use the epmremoteclient and send a 'saveandexit x' where x is the timeout in minutes. a 0 will stop it immediately.
        return self.epmrcExecute(commands=["run"], payload=f"saveandexit {timeout}")
