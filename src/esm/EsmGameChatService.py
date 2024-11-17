from functools import cached_property
import json
import logging
import csv
from pathlib import Path
import queue
import random
import subprocess
import threading
import time
from typing import Optional, Union

from pydantic import BaseModel
from esm.ConfigModels import MainConfig
from esm.DataTypes import ChatMessage
from esm.EsmConfigService import EsmConfigService
from esm.EsmEpmRemoteClientService import EsmEpmRemoteClientService
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
        class that handles the communication with egs via the epmrc tool
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
    def epmClient(self) -> EsmEpmRemoteClientService:
        return ServiceRegistry.get(EsmEpmRemoteClientService)

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
        """Starts the reader process and begins capturing output"""
        epmrcPath = self.epmClient.checkAndGetEpmRemoteClientPath().absolute()
        self._readerProcess = subprocess.Popen(
            args=[epmrcPath, "listen", "-q", "-o", "json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        def _eventReaderThread():
            while not self._shouldStop and self._readerProcess.poll() is None:
                line = self._readerProcess.stdout.readline()
                if line:
                    message = self._parseEvent(line)
                    if message:
                        self._incomingMessages.put(message)
            if self._readerProcess.poll() is None:
                self._readerProcess.terminate()
                
        self._eventReaderThread = threading.Thread(target=_eventReaderThread, daemon=True).start()
    
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
            actually sends a message via epmrc
        """
        if message.speaker == "hAImster":
            log.info(f"Received message from hAImster: {message.message}")
            self.epmClient.sendServerChat(f"{message.speaker}: {message.message}")
        else:
            self.epmClient.sendMessage(message.speaker, message.message)
  
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
