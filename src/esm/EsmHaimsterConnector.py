import logging
import queue
import threading
import time
import uvicorn
import requests
from functools import cached_property
from http.client import HTTPException
from fastapi import FastAPI
from typing import Dict

from esm.ConfigModels import MainConfig
from esm.DataTypes import ChatMessage
from esm.EsmConfigService import EsmConfigService
from esm.EsmDatabaseWrapper import EsmDatabaseWrapper
from esm.EsmGameChatService import EgsChatMessageEvent, EsmGameChatService
from esm.EsmLogger import EsmLogger
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
    _allPlayers: Dict[int, str] = {}
    _allPlayersLastUpdate: float = None

    _fastApiApp = FastAPI()
    _httpServer: uvicorn.Server = None
    _httpServerWorker: threading.Thread = None
    _shouldExit = threading.Event()

    @cached_property
    def config(self) -> MainConfig:
        return ServiceRegistry.get(EsmConfigService).config

    @cached_property
    def esmGameChatService(self) -> EsmGameChatService:
        return ServiceRegistry.get(EsmGameChatService)
    
    def initialize(self):
        """
            initializes and starts the connector. 
            returns an even that you can set to force the connector to shut down (or just use the shutdown() method)
        """
        if not self.config.communication.haimsterEnabled:
            return
        log.info("Initializing haimster connector")
        self.esmGameChatService.initialize()
        self._startIncomingChatMessageHandler()
        self._startOutgoingChatResponseHandler()
        self._startHttpServer()
        self.sendOutgoingChatResponse(ChatMessage(speaker="hAImster", message="connected!", timestamp=time.time()))

        # register fastapi routes
        @self._fastApiApp.post("/outgoingmessage")
        async def sendResponse(message: ChatMessage):
            self.sendOutgoingChatResponse(message)
            return {"status": "success"}
        
        return self._shouldExit
        
    def _startHttpServer(self):
        """
            Starts the FastAPI server in a background thread
        """
        host = self.config.communication.incomingMessageHostIp
        port = self.config.communication.incomingMessageHostPort
        def runHttpServer():
            config = uvicorn.Config(
                app=self._fastApiApp,
                host=host,
                port=port,
                loop="auto",
                log_config=None
            )
            self._httpServer = uvicorn.Server(config)
            #self._httpServer.install_signal_handlers = lambda: None
            self._httpServer.run()

        self._httpServerWorker = threading.Thread(target=runHttpServer, daemon=True)
        self._httpServerWorker.start()
        log.info(f"HTTP server for haimster messages started on http://{host}:{port}")


    def _shutdownHttpServer(self):
        """
            Clean shutdown of the game server and HTTP server
        """
        self._shouldExit.set()
        log.info("HTTP server for haimster messages shutting down...")
        if self._httpServerWorker and self._httpServerWorker.is_alive():
            log.info("Shutting down HTTP server...")
            self._httpServer.shutdown()
            self._httpServerWorker.join()
 

    def shutdown(self):
        """
            stop any threads and services belonging to the connector
        """
        if not self.config.communication.haimsterEnabled:
            return
        log.info("Shutting down haimster connector")
        self._shutdownHttpServer()
        self.sendOutgoingChatResponse(ChatMessage(speaker="hAImster", message="disconnecting...", timestamp=time.time()))
        self._incomingChatMessageHandlerShouldStop.set()
        self._outgoingChatResponseHandlerShouldStop.set()
        self.esmGameChatService.shutdown()
        log.info("haimster connector shut down")


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
            log.error(f"Error sending chat message to haimster: {str(e)}", e)

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
                raise HTTPException(f"Could not send message to haimster: {response.status_code}")
        except Exception as e:
            raise HTTPException(f"Error communicating with chatbot server: {str(e)}", e)
        
    def _getPlayerName(self, playerId: int):
        """
            returns the playername for the given playerId, if not found, returns "Player_{playerId}"
            the results will be cached for the configured cache time
        """
        cacheTime = self.config.communication.playerNameCacheTime
        if len(self._allPlayers) < 1 or time.time() - self._allPlayersLastUpdate > cacheTime:
            dbWrapper = EsmDatabaseWrapper()
            self._allPlayers = dbWrapper.retrieveAllPlayerEntities()
            self._allPlayersLastUpdate = time.time()
            dbWrapper.closeDbConnection()
        return self._allPlayers.get(playerId, f"Player_{playerId}")