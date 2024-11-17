import asyncio
from contextlib import asynccontextmanager
from functools import partial
import json
import signal
import subprocess
import threading
import queue
from typing import Optional, Union
import time
import logging
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from egs_playerids import PlayerInformationProvider

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

class ChatMessage(BaseModel):
    timestamp: float
    speaker: str
    message: str

class EgsChatData(BaseModel):
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
    CmdId: Union[str | int] # e.g. Event_ChatMessage or some integer if emprc can't deserialize it
    SeqNum: int # seems to be always 201 for some reason
    Data: EgsChatData # the chat info

class EgsChatHandler:
    """
        class that handles the communication with egs via the epmrc tool
    """
    def __init__(self, exe_path: str):
        self._exePath = exe_path
        self._incomingMessages = queue.Queue()
        self._outgoingMessages = queue.Queue()
        self._readerProcess: Optional[subprocess.Popen] = None
        self._eventReaderThread: threading.Thread = None
        self._chatPosterThread: threading.Thread = None
        self._shouldStop = False

    def initialize(self):
        self._startEventReader()
        self._startChatPoster()
        
    def _startEventReader(self):
        """Starts the reader process and begins capturing output"""
        self._readerProcess = subprocess.Popen(
            args=[self._exePath, "listen", "-q", "-o", "json"],
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
            args=[self._exePath, "run", "-q", f"say '{self._safeString(message.speaker)}: {self._safeString(message.message)}'"]
        else:
            args=[self._exePath, "chat-message", "-q", "--sender-name", f"{message.speaker}", f"{message.message}"]
        return subprocess.Popen(args=args)
    
    def _safeString(self, string: str) -> str:
        return string.replace("'", "").replace('"', '')
   
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
    
    def shutdown(self):
        """Stops both processes and their threads"""
        self._shouldStop = True
        
        if self._readerProcess:
            self._readerProcess.terminate()

class HaimsterConnector():
    """
        class that handles the communication with haimster
        It will ask the egs chat handler for incoming chat messages and send them to haimster
        It will watch a queue of responses from haimster and send them to the egs chat handler
    """
    def __init__(self, chatserverhost: str, egsChatHandler: EgsChatHandler, playerInformationProvider: PlayerInformationProvider):
        self._haimsterhost = chatserverhost
        
        self._egsChatHandler = egsChatHandler
        self._playerInformationProvider = playerInformationProvider

        self._incomingChatMessageHandlerThread: threading.Thread = None
        self._incomingChatMessageHandlerShouldStop: threading.Event = threading.Event()

        self._outgoingResponsesQueue = queue.Queue()
        self._outgoingChatResponseHandlerThread: threading.Thread = None
        self._outgoingChatResponseHandlerShouldStop: threading.Event = threading.Event()

    def initialize(self):
        self._egsChatHandler.initialize()
        self._playerInformationProvider.initialize()
        self._startIncomingChatMessageHandler()
        self._startOutgoingChatResponseHandler()
        self.sendOutgoingChatResponse(ChatMessage(speaker="hAImster", message="connected!", timestamp=time.time()))

    def shutdown(self):
        self.sendOutgoingChatResponse(ChatMessage(speaker="hAImster", message="disconnecting...", timestamp=time.time()))
        self._incomingChatMessageHandlerShouldStop.set()
        self._outgoingChatResponseHandlerShouldStop.set()
        self._egsChatHandler.shutdown()

    def _startIncomingChatMessageHandler(self):
        def _incomingChatMessageHandler():
            while not self._incomingChatMessageHandlerShouldStop.is_set():
                try:
                    message = self._egsChatHandler.getMessage(timeout=1)
                    if message:
                        self._sendIncomingChatMessageToHaimster(message)
                except queue.Empty:
                    continue
        self._incomingChatMessageHandlerThread = threading.Thread(target=_incomingChatMessageHandler, daemon=True).start()

    def _startOutgoingChatResponseHandler(self):
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
        self._egsChatHandler.sendMessage(speaker=response.speaker, message=response.message)

    def sendOutgoingChatResponse(self, response: ChatMessage):
        self._outgoingResponsesQueue.put(response)
        
    def _sendIncomingChatMessageToHaimster(self, message: EgsChatMessageEvent):
        try:
            playerId = message.Data.playerId
            playerName = self._playerInformationProvider.getPlayerName(playerId)
            if not playerName:
                playerName = f"Player_{playerId}"
            chatMessage = ChatMessage(speaker=playerName, message=message.Data.msg, timestamp=time.time())
            self._sendToHaimster(chatMessage)
        except Exception as e:
            log.error(f"Error sending chat message to haimster: {str(e)}")

    def _sendToHaimster(self, message: ChatMessage):
        """
            sends a message to haimster
        """
        try:
            response = requests.post(
                url=self._haimsterhost +"/message",
                json={"speaker": message.speaker, "message": message.message, "timestamp": message.timestamp}
            )
            if response.status_code != 200 and response.status_code != 204:
                raise HTTPException(status_code=response.status_code, detail="Chatbot server error")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error communicating with chatbot server: {str(e)}")

############## global stuff

connector: HaimsterConnector = None

def signal_handler(signum, frame, app):
    # shutdown application
    shutdownEvent()
    # deregister function from signal (by registering default handlers)
    signal.signal(signum, signal.SIG_DFL)
    # re-raise a signal event to shut down everything that's lurking around
    signal.raise_signal(signum)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
        fastapi lifespan handler for application lifecycle
    """
    log.info("Application lifespan startup")

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, partial(signal_handler, app=app))
    signal.signal(signal.SIGTERM, partial(signal_handler, app=app))
    yield

def shutdownEvent():
    log.info("Application lifespan shutdown")
    # Notify clients of the shutdown
    #loop = asyncio.get_event_loop()
    #loop.create_task(connector.shutdown)
    connector.shutdown()
    time.sleep(.5)

app = FastAPI(lifespan=lifespan)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/outgoingmessage")
async def sendResponse(message: ChatMessage):
    connector.sendOutgoingChatResponse(message)
    return {"status": "success"}

# Example usage
if __name__ == "__main__":
    db_path = r"d:\Servers\Empyrion\Saves\Games\EsmDediGame\global.db"
    handler = EgsChatHandler("EmpyrionPrime.RemoteClient.Console.exe")
    provider = PlayerInformationProvider(db_path)
    connector = HaimsterConnector("http://192.168.1.102:8000", handler, provider)
    connector.initialize()

    uvicorn.run(app, host="192.168.122.30", port=9000)
