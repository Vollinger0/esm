import logging
import logging.config
import queue
import threading
import time
import uvicorn
import requests
from functools import cached_property
from http.client import HTTPException
from fastapi import FastAPI

from esm.ConfigModels import MainConfig
from esm.DataTypes import ChatMessage
from esm.EsmConfigService import EsmConfigService
from esm.EsmGameChatService import EsmGameChatService
from esm.ServiceRegistry import Service, ServiceRegistry

log = logging.getLogger(__name__)
logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

@Service
class EsmHaimsterConnector:
    """
        Service that handles the communication with haimster and the egs ingame chat via the EsmGameChatService.

        It will ask the EsmGameChatService for incoming chat messages and send them to haimster
        It will listen to an http endpoint for outgoing responses from haimster and send them to the EsmGameChatService

        It uses queues and worker threads internally for serial processing and control
    """
    _incomingChatMessageHandlerThread: threading.Thread = None
    _incomingChatMessageHandlerShouldStop: threading.Event = threading.Event()
    _messageQueueToEgsChat = queue.Queue()
    _outgoingChatResponseHandlerThread: threading.Thread = None
    _outgoingChatResponseHandlerShouldStop: threading.Event = threading.Event()

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
        log.info("Initializing haimster connector")
        self.esmGameChatService.initialize()
        
        self._startIncomingChatMessageHandler()
        
        self._startOutgoingChatResponseHandler()
        log.info(f"haimster host set to: {self.config.communication.haimsterHost}")

        host = self.config.communication.incomingMessageHostIp
        port = self.config.communication.incomingMessageHostPort
        self._startHttpServer(host, port)
        log.info(f"HTTP server container for receiving haimster messages started on http://{host}:{port}")

        # send welcome message
        haimsterConnectedMessage = self.config.communication.haimsterConnectedMessage
        self.queueChatMessageForEgsChat(ChatMessage(speaker="hAImster", message=haimsterConnectedMessage, timestamp=time.time()))

        # register fastapi routes
        @self._fastApiApp.post("/outgoingmessage")
        async def sendResponse(message: ChatMessage):
            self.queueChatMessageForEgsChat(message)
            return {"status": "success"}
        
        return self._shouldExit
        
    def _startHttpServer(self, host: str, port: int):
        """
            Starts the FastAPI server in a separate worker thread
        """
        def runHttpServer():
            logging.getLogger("uvicorn").setLevel(logging.WARNING)
            config = uvicorn.Config(
                app=self._fastApiApp,
                host=host,
                port=port,
                log_config=None,
            )
            self._httpServer = uvicorn.Server(config)
            self._httpServer.run()
            # if log.getEffectiveLevel() == logging.DEBUG:
            #     EsmLogger.configureUvicornLogging(logLevel=logging.INFO)
            # else:
            #     EsmLogger.configureUvicornLogging(logLevel=logging.WARNING)

        self._httpServerWorker = threading.Thread(target=runHttpServer, daemon=True)
        self._httpServerWorker.start()


    def _shutdownHttpServer(self):
        """
            Clean shutdown of the worker threads and HTTP server
        """
        self._shouldExit.set()
        log.info("HTTP server for haimster messages shutting down...")
        if self._httpServerWorker and self._httpServerWorker.is_alive():
            log.info("Shutting down HTTP server...")
            # for some reason, the shutdown method on the uvicorn server doesn't work properly
            self._httpServer.should_exit = True
            # in doubt, wait for the worker thread to finish, but not for too long
            self._httpServerWorker.join(timeout=5)
 

    def shutdown(self):
        """
            stop any threads and services belonging to the connector
        """
        log.info("Shutting down haimster connector")
        self._shutdownHttpServer()
        haimsterDisconnectedMessage = self.config.communication.haimsterDisconnectedMessage
        self.queueChatMessageForEgsChat(ChatMessage(speaker="hAImster", message=haimsterDisconnectedMessage, timestamp=time.time()))
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
                        self._sendChatMessageToHaimster(message)
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
                    response = self._messageQueueToEgsChat.get(timeout=1)
                    if response:
                        self._sendChatMessageToEgsChat(response)
                except queue.Empty:
                    continue
        self._outgoingChatResponseHandlerThread = threading.Thread(target=_outgoingChatResponseHandler, daemon=True).start()


    def _sendChatMessageToEgsChat(self, response: ChatMessage):
        """
            actually sened a haimster response to the game chat
        """
        self.esmGameChatService.sendMessage(speaker=response.speaker, message=response.message)


    def queueChatMessageForEgsChat(self, response: ChatMessage):
        """
            adds a haimster response to the outgoing queue
        """
        self._messageQueueToEgsChat.put(response)
        

    def _sendChatMessageToHaimster(self, message: ChatMessage):
        """
            sends a message to haimster
        """
        haimsterhost = self.config.communication.haimsterHost
        try:
            response = requests.post(
                url=haimsterhost +"/message",
                json={"speaker": message.speaker, "message": message.message, "timestamp": message.timestamp},
                timeout=5,
            )
            if response.status_code != 200 and response.status_code != 204:
                raise HTTPException(f"Could not send message to haimster, response code is: {response.status_code}")
        except Exception as e:
            log.error(f"Error sending chat message to haimster: {str(e)}")
