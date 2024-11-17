from functools import cached_property
from http.client import HTTPException
import logging
import queue
import threading
import time
from typing import Dict

import requests
from esm.ConfigModels import MainConfig
from esm.DataTypes import ChatMessage
from esm.EsmConfigService import EsmConfigService
from esm.EsmDatabaseWrapper import EsmDatabaseWrapper
from esm.EsmGameChatService import EgsChatMessageEvent, EsmGameChatService
from esm.ServiceRegistry import Service, ServiceRegistry

log = logging.getLogger(__name__)

@Service
class EsmHaimsterConnector:
    """
        class that handles the communication with haimster
        It will ask the EsmGameChatService for incoming chat messages and send them to haimster
        It will watch a queue of responses from haimster and send them to the EsmGameChatService
    """
    _incomingChatMessageHandlerThread: threading.Thread = None
    _incomingChatMessageHandlerShouldStop: threading.Event = threading.Event()
    _outgoingResponsesQueue = queue.Queue()
    _outgoingChatResponseHandlerThread: threading.Thread = None
    _outgoingChatResponseHandlerShouldStop: threading.Event = threading.Event()
    _allPlayers: Dict[int, str]
    _allPlayersLastUpdate: float

    @cached_property
    def config(self) -> MainConfig:
        return ServiceRegistry.get(EsmConfigService).config

    @cached_property
    def esmGameChatService(self) -> EsmGameChatService:
        return ServiceRegistry.get(EsmGameChatService)
    
    @cached_property
    def esmDatabaseWrapper(self) -> EsmDatabaseWrapper:
        return ServiceRegistry.get(EsmDatabaseWrapper)

    def initialize(self):
        if not self.config.communication.haimsterEnabled:
            return
        log.info("Initializing haimster connector")
        self.esmGameChatService.initialize()
        self._startIncomingChatMessageHandler()
        self._startOutgoingChatResponseHandler()
        self.sendOutgoingChatResponse(ChatMessage(speaker="hAImster", message="connected!", timestamp=time.time()))

    def shutdown(self):
        if not self.config.communication.haimsterEnabled:
            return
        log.info("Shutting down haimster connector")
        self.sendOutgoingChatResponse(ChatMessage(speaker="hAImster", message="disconnecting...", timestamp=time.time()))
        self._incomingChatMessageHandlerShouldStop.set()
        self._outgoingChatResponseHandlerShouldStop.set()
        self.esmGameChatService.shutdown()

    def _startIncomingChatMessageHandler(self):
        """
            starts the new worker thread that checks for incoming messages from the EsmGameChatService in a 1 second loop to send them to haimster
        """
        def _incomingChatMessageHandler():
            while not self._incomingChatMessageHandlerShouldStop.is_set():
                try:
                    message = self.esmGameChatService.getMessage(timeout=1)
                    if message:
                        self._sendIncomingChatMessageToHaimster(message)
                except queue.Empty:
                    continue
        self._incomingChatMessageHandlerThread = threading.Thread(target=_incomingChatMessageHandler, daemon=True).start()

    def _startOutgoingChatResponseHandler(self):
        """
            starts the new worker thread that checks for outgoing messages from haimster in a 1 second loop to send them to the egs chat
        """
        def _outgoingChatResponseHandler():
            while not self._outgoingChatResponseHandlerShouldStop.is_set():
                try:
                    response = self._outgoingResponsesQueue.get(timeout=1)
                    if response:
                        self._sendOutgoingChatResponseToEgsChat(response)
                except queue.Empty:
                    continue
        self._outgoingChatResponseHandlerThread = threading.Thread(target=_outgoingChatResponseHandler, daemon=True).start()

    def _sendOutgoingChatResponseToEgsChat(self, response: ChatMessage):
        self.esmGameChatService.sendMessage(speaker=response.speaker, message=response.message)

    def sendOutgoingChatResponse(self, response: ChatMessage):
        self._outgoingResponsesQueue.put(response)
        
    def _sendIncomingChatMessageToHaimster(self, message: EgsChatMessageEvent):
        try:
            playerId = message.Data.playerId
            playerName = self._getPlayerName(playerId)
            chatMessage = ChatMessage(speaker=playerName, message=message.Data.msg, timestamp=time.time())
            self._sendToHaimster(chatMessage)
        except Exception as e:
            log.error(f"Error sending chat message to haimster: {str(e)}")

    def _sendToHaimster(self, message: ChatMessage):
        """
            sends a message to haimster
        """
        haimsterhost = self.config.communication.haimsterHost
        try:
            response = requests.post(
                url=haimsterhost +"/message",
                json={"speaker": message.speaker, "message": message.message, "timestamp": message.timestamp}
            )
            if response.status_code != 200 and response.status_code != 204:
                raise HTTPException(status_code=response.status_code, detail="Chatbot server error")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error communicating with chatbot server: {str(e)}")
        
    def _getPlayerName(self, playerId: int):
        """
            returns the playername for the given playerId, if not found, returns "Player_{playerId}"
            the results will be cached for the configured cache time
        """
        cacheTime = self.config.communication.playerNameCacheTime
        if self._allPlayersLastUpdate and self._allPlayersLastUpdate < time.time() - cacheTime:
            self._allPlayers = self.esmDatabaseWrapper.retrieveAllPlayerEntities()
            self._allPlayersLastUpdate = time.time()
        return self._allPlayers.get(playerId, f"Player_{playerId}")
