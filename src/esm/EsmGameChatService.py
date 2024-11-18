from datetime import datetime
from functools import cached_property
import json
import logging
from pathlib import Path
import queue
import subprocess
import threading
import time
from typing import List, Optional, Union

from pydantic import BaseModel
from esm.ConfigModels import MainConfig
from esm.DataTypes import ChatMessage
from esm.EsmConfigService import EsmConfigService
from esm.EsmDatabaseWrapper import EsmDatabaseWrapper
from esm.EsmEmpRemoteClientService import EsmEmpRemoteClientService
from esm.ServiceRegistry import Service, ServiceRegistry

log = logging.getLogger(__name__)

class EgsChatData(BaseModel):
    """
        data type for egs chat data, part of chat message events
    """
    playerId: int # player entity id
    msg: str # message
    recipientEntityId: int # only set for private chat
    recipientFactionId: int # only set in faction chat
    # message types:
    # 3 = global
    # 5 & rFid > 0 = faction
    # 5 & rfId == 0 = alliance
    # 8 = private
    # 9 = server 
    type: int # message type (see above)

class EgsChatMessageEvent(BaseModel):
    """
        data type for egs chat message events
    """
    CmdId: Union[str | int] # e.g. Event_ChatMessage or some integer if emprc can't deserialize it
    SeqNum: int # seems to be always 201 for some reason
    Data: EgsChatData


@Service
class EsmGameChatService:
    """
        class that handles the ingame chat communication with egs via the emprc tool
        it will do so using queues and separate threads handling the reading and writing
        but provides two simple methods for interaction with the chat.
    """
    _incomingMessages = queue.Queue()
    _outgoingMessages = queue.Queue()
    _readerProcess: Optional[subprocess.Popen] = None
    _eventReaderThread: threading.Thread = None
    _chatPosterThread: threading.Thread = None
    _shouldStop = False

    @cached_property
    def config(self) -> MainConfig:
        return ServiceRegistry.get(EsmConfigService).config
    
    @cached_property
    def emprcClient(self) -> EsmEmpRemoteClientService:
        return ServiceRegistry.get(EsmEmpRemoteClientService)

    def initialize(self):
        log.info("Initializing chat service")
        self._startEventReader()
        self._startChatPoster()

    def shutdown(self):
        """Stops both processes and their threads"""
        log.info("Shutting down chat service")
        self._shouldStop = True

        if self._readerProcess:
            self._readerProcess.terminate()

    def _startEventReader(self):
        """
            Starts the emprc event reader process and begins capturing output in a separate worker thread
            If emprc can not be started, this will keep restarting it until it stops failing
        """
        def _startEmpRcListeningProcess():
            emprcPath = self.emprcClient.checkAndGetEmpRemoteClientPath().absolute()
            return subprocess.Popen(
                args=[emprcPath, "listen", "-q", "-o", "json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

        def _eventReaderThread():
            log.debug("Starting emprc event reader thread")
            retryDelay=10
            while not self._shouldStop:
                try:
                    self._readerProcess = _startEmpRcListeningProcess()
                    while not self._shouldStop and self._readerProcess.poll() is None:
                        line = self._readerProcess.stdout.readline()
                        if line:
                            log.debug(f"Received message: {line}")
                            message = self._parseEvent(line)
                            if message:
                                self._incomingMessages.put(message)
                    # Process has ended - check if it was due to an error
                    exitCode = self._readerProcess.poll()
                    if exitCode is not None and exitCode != 0:
                        raise subprocess.SubprocessError(f"Process failed with exit code {exitCode}, could not listen to egs events via emprc")
                except (subprocess.SubprocessError, IOError) as e:
                    log.error(e)
                    if self._shouldStop:
                        break
                    log.info(f"Attempting to connect with emprc again in {retryDelay} seconds...")
                    # Clean up the failed process if it's still running
                    if hasattr(self, '_readerProcess') and self._readerProcess.poll() is None:
                        try:
                            self._readerProcess.terminate()
                            self._readerProcess.wait(timeout=5)
                        except (subprocess.TimeoutExpired, Exception) as term_error:
                            log.error(f"Error terminating process: {str(term_error)}")
                            try:
                                self._readerProcess.kill()
                            except Exception as kill_error:
                                log.error(f"Error killing process: {str(kill_error)}")
                    
                    # Wait before retrying
                    time.sleep(retryDelay)
                    continue
                    
            # Clean up when stopping
            if hasattr(self, '_readerProcess') and self._readerProcess.poll() is None:
                self._readerProcess.terminate()
            log.debug("EGS emprc event reader thread stopped")

        self._eventReaderThread = threading.Thread(target=_eventReaderThread, daemon=True)
        self._eventReaderThread.start()         
    
    def _parseEvent(self, line: str) -> Optional[EgsChatMessageEvent]:
        """
            Tries to parse a line into an EgsChatMessageEvent, only if it is of type Event_ChatMessage
        """
        try:
            event = json.loads(line)
            if event["CmdId"] == "Event_ChatMessage":
                return EgsChatMessageEvent.model_validate_json(line)
        except json.JSONDecodeError:
            log.error(f"Error parsing JSON: {line}")
        return None

    def _startChatPoster(self):
        """Starts the writer process and begins processing the outgoing message queue"""
        
        def _chatPosterThread():
            while not self._shouldStop:
                try:
                    # Wait for a message with frequent timeouts to be able to shutdown
                    message = self._outgoingMessages.get(timeout=1)
                    self._postChatmessage(message)
                    time.sleep(0.1)  # Small delay between messages
                except queue.Empty:
                    continue
             
        self._chatPosterThread = threading.Thread(target=_chatPosterThread, daemon=True).start()

    def _postChatmessage(self, message: ChatMessage):
        """
            actually sends a message via emprc
        """
        if message.speaker == "hAImster":
            log.info(f"Received message from hAImster: {message.message}")
            self.emprcClient.sendServerChat(f"{message.speaker}: {message.message}")
        else:
            self.emprcClient.sendMessage(senderName=message.speaker, message=message.message)
  
    def sendMessage(self, speaker: str, message: str):
        """Adds a message to the outgoing queue"""
        message = ChatMessage(speaker=speaker, message=message, timestamp=time.time())
        self._outgoingMessages.put(message)
    
    def getMessage(self, block: bool = True, timeout: Optional[float] = None) -> EgsChatMessageEvent:
        """
            Gets a message from the incoming queue, usually blocking - set a timeout if using in a loop
        """
        try:
            return self._incomingMessages.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
        
    def exportChatLog(self, dbFilePath: Path=None, filename: str="chatlog.json", format: str="json", excludeNames: List[str] = [], includeNames: List[str] = []):
        """
            Exports the chat log for current or given database to a the file system, with the specified format
        """
        dbWrapper = EsmDatabaseWrapper(dbFilePath)
        chatlog = dbWrapper.retrieveFullChatlog()
        filenamePath = Path(Path(filename).stem + "." + format)
        cleanChatLog = list()
        if len(includeNames) > 0:
            for message in chatlog:
                if message['speaker'] in includeNames:
                    cleanChatLog.append(message)
        else:
            # also always exclude the sync event announcer
            excludeNames.append(self.config.communication.synceventname)
            for message in chatlog:
                if message['speaker'] not in excludeNames:
                    cleanChatLog.append(message)

        if format == "json":
            with open(filenamePath, "w") as f:
                for message in cleanChatLog:
                    time = datetime.fromtimestamp(message['timestamp']).isoformat(timespec='seconds')
                    speaker = message['speaker']
                    message = message['message']
                    line = {"time": time, "speaker": speaker, "message": message}
                    f.write(f"{json.dumps(line)}\n")
        elif format == "text":
            with open(filenamePath, "w") as f:
                for message in cleanChatLog:
                    timestamp = datetime.fromtimestamp(message['timestamp']).isoformat(timespec='seconds')
                    f.write(f"{timestamp} {message['speaker']}: {message['message']}\n")
        else:
            raise ValueError(f"Unsupported format specification for download: {format}")
        dbWrapper.closeDbConnection()
        log.info(f"Chat log exported to '{filenamePath.absolute()}'")
        return filenamePath.absolute()
