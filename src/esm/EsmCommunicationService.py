from enum import Enum
from functools import cached_property
import logging
import csv
from pathlib import Path
import random
from esm.EsmConfigService import EsmConfigService
from esm.EsmEpmRemoteClientService import EsmEpmRemoteClientService
from esm.ServiceRegistry import Service, ServiceRegistry

log = logging.getLogger(__name__)

@Service
class EsmCommunicationService:
    """
    provides methods to for server chat communication
    """
    @cached_property
    def config(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)
    
    @cached_property
    def epmClient(self) -> EsmEpmRemoteClientService:
        return ServiceRegistry.get(EsmEpmRemoteClientService)

    @cached_property
    def syncName(self):
        return self.config.communication.synceventname

    @cached_property    
    def syncChatLines(self):
        return self.getSyncChatLines()
    
    def announceSyncStart(self):
        """used to announce a starting sync on the server via chat message"""
        startMessage, endMessage = self.getRandomSyncChatLine()
        self.currentSyncLineStart = startMessage
        self.currentSyncLineEnd = endMessage
        self.epmClient.sendMessage(self.syncName, self.currentSyncLineStart)

    def announceSyncEnd(self):
        """used to announce that a sync ended on the server via chat message"""
        if self.currentSyncLineEnd is None:
            log.debug("for some reason the endsync line is not set, get a random one then")
            startMessage, endMessage = self.getRandomSyncChatLine()
            self.currentSyncLineEnd = endMessage
        self.epmClient.sendMessage(self.syncName, self.currentSyncLineEnd)
        # reset the current sync lins so the don't get reused.
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
        syncEventsFilePath = Path(self.config.communication.synceventsfile).resolve().absolute()

        data = []
        if not syncEventsFilePath.exists():
            log.warning(f"The configured file {syncEventsFilePath} does not exist, will not be able to send messages on sync events.")

        with open(syncEventsFilePath, "r") as file:
            csvReader = csv.reader(file, delimiter=',', quotechar='"', doublequote=True)
            for index, row in enumerate(csvReader):
                if len(row) == 2:
                    start, end = row
                    data.append((start,end))
                else:
                    log.warning(f"{syncEventsFilePath} contains an invalid line at line {index}. Will ignore that line.")
        return data