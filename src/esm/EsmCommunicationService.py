import logging
import csv
import random

from functools import cached_property
from pathlib import Path
from esm.ConfigModels import MainConfig
from esm.EsmConfigService import EsmConfigService
from esm.EsmEpmRemoteClientService import EsmEpmRemoteClientService
from esm.ServiceRegistry import Service, ServiceRegistry

log = logging.getLogger(__name__)

@Service
class EsmCommunicationService:
    """
    provides methods for server chat communication
    """
    @cached_property
    def config(self) -> MainConfig:
        return ServiceRegistry.get(EsmConfigService).config
    
    @cached_property
    def epmClient(self) -> EsmEpmRemoteClientService:
        return ServiceRegistry.get(EsmEpmRemoteClientService)

    @cached_property    
    def syncChatLines(self):
        return self.getSyncChatLines()
    
    def shallAnnounceSync(self):
        """
        returns true if announceSyncEvents is enabled and the random roll was above the configured probabilty 
        """
        if self.config.communication.announceSyncEvents:
            probability = self.config.communication.announceSyncProbability 
            return random.random() < probability
        return False
    
    def announceSyncStart(self):
        """used to announce a starting sync on the server via chat message"""
        self.config.communication.synceventmessageprefix
        startMessage, endMessage = self.getRandomSyncChatLine()
        self.currentSyncLineStart = self.config.communication.synceventmessageprefix + startMessage
        self.currentSyncLineEnd = self.config.communication.synceventmessageprefix + endMessage
        self.epmClient.sendMessage(senderName=self.config.communication.synceventname, message=self.currentSyncLineStart)

    def announceSyncEnd(self):
        """used to announce that a sync ended on the server via chat message"""
        if self.currentSyncLineEnd is None:
            log.warning("for some reason the endsync line is not set, get a random one then")
            startMessage, endMessage = self.getRandomSyncChatLine()
            self.currentSyncLineEnd = self.config.communication.synceventmessageprefix + endMessage
        self.epmClient.sendMessage(senderName=self.config.communication.synceventname, message=self.currentSyncLineEnd)
        # reset the current sync lines so the don't get reused.
        self.currentSyncLineStart = None
        self.currentSyncLineEnd = None

    def getRandomSyncChatLine(self):
        """returns the start and end line of a random line in the sync file"""
        chatLines = self.syncChatLines
        start, end = random.choice(chatLines)
        return start, end

    def getSyncChatLines(self):
        """
        returns all the lines from the sync event file as a list, or an empty one if something didn't work.
        """
        syncEventsFilePath = Path(self.config.communication.synceventsfile).resolve()

        data = []
        if not syncEventsFilePath.exists():
            log.warning(f"The configured file {syncEventsFilePath} does not exist, will not be able to send messages on sync events.")

        with open(syncEventsFilePath, "r") as file:
            #csvReader = csv.reader(file, delimiter=',', quotechar='"', doublequote=True, skipinitialspace=True)
            csvReader = csv.reader(file, skipinitialspace=True)
            for index, row in enumerate(csvReader):
                if len(row) == 2:
                    start, end = row
                    data.append((start,end))
                else:
                    log.warning(f"{syncEventsFilePath} contains an invalid line at line {index} - it contains {len(row)} columns. Will ignore that line.")
        return data
