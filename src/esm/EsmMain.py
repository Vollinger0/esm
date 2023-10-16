import logging
from pathlib import Path
import time
from halo import Halo
from psutil import TimeoutExpired
from esm import AdminRequiredException, askUser
from esm.EsmFileSystem import EsmFileSystem
from esm.EsmLogger import EsmLogger
from esm.EsmConfig import EsmConfig
from esm.EsmDedicatedServer import EsmDedicatedServer
from esm.EsmRamdiskManager import EsmRamdiskManager

log = logging.getLogger(__name__)

class EsmMain:
    """
    Main esm class, manages all the other modules, config, etc.
    """

    def __init__(self, installDir, configFileName, caller=__name__):
        # bootstrap
        self.logFile = Path(caller).stem + ".log"
        EsmLogger.setUpLogging(self.logFile)
        configFilePath = Path(f"{installDir}/{configFileName}").absolute()
        self.config = self.createEsmConfig(configFilePath)

        # extend the config with some context information
        contextMap = {
                    'installDir': installDir,
                    'configFileName': configFileName,
                    'caller': caller,
                    'logFile': self.logFile,
                    'configFilePath': configFilePath
                }
        self.config.context.update(contextMap)

        # create instances
        self.dedicatedServer = self.createDedicatedServer()
        self.fileStructure = self.createEsmFileStructure()
        self.ramdiskManager = self.createEsmRamdiskManager(self.dedicatedServer)

    def createEsmConfig(self, configFilePath):
        return EsmConfig.fromConfigFile(configFilePath)

    def createDedicatedServer(self):
        return EsmDedicatedServer.withConfig(self.config)
    
    def createEsmFileStructure(self):
        return EsmFileSystem(self.config)
    
    def createEsmRamdiskManager(self, dedicatedServer):
        return EsmRamdiskManager(self.config, dedicatedServer)
    
    def askUserToCreateNewSavegame(self):
        if askUser("Do you want to create a new savegame? [yes/no] ", "yes"):
            log.debug("creating new savegame")
            self.createNewSavegame()
            return True
        return False

    def createNewSavegame(self):
        """
        will start the server shortly to create a new savegame that can be used for installation
        """
        log.info("Will start the server with its blue graphics overlay to create a new savegame. The startup might take a few minutes.")
        # log.info("You'll probably need to stop it again once you see the button 'Save and Exit' next to the 'Say' button and input field. It takes a bit to appear.")
        log.info("This script will shut down the server automatically again, if it doesn't work, you'll probably have to stop it yourself by clicking on the 'Save and Exit' button.")
        if askUser("Ready? [yes/no] ", "yes"):
            log.info("Will start the server with the default configuration now")
            newEsm = EsmDedicatedServer.withGfxMode(self.config, EsmDedicatedServer.GFXMODE_ON)
            try:
                newEsm.startServer()
                # give the server some time to start and create the new savegame before we try stopping it again
                time.sleep(self.config.server.startUpSleepTime)
                try:
                    # use the epmclient to check when the server is up and send a saveandexit from there.
                    newEsm.sendExitRetryAndWait()
                except TimeoutError as ex:
                    log.error(f"could not stop server while trying to create a new savegame. Something's wrong")
                    raise AdminRequiredException("could not stop server while trying to create a new savegame.")
            except Exception as ex:
                log.info(f"Server didn't start: {ex}")
        else:
            log.info("Create a new savegame yourself then, you can always start this installation again.")

    def askUserToDeleteOldSavegameMirror(self):
        """
        ask user if he wants to the delete the old savegame mirror and do that if yes        
        """
        savegameMirrorPath = self.fileStructure.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
        if askUser(f"Delete old savegame mirror at {savegameMirrorPath}? [yes/no] ", "yes"):
            self.fileStructure.quickDelete(savegameMirrorPath)
            return True
        return False
    
    def startServer(self):
        """
        Will start the server and the ramdisk synchronizer
        """
        # start the synchronizer
        syncInterval = self.config.ramdisk.synchronizeramtohddinterval
        if syncInterval>0:
            log.info(f"Starting ram2mirror synchronizer with interval {syncInterval}")
            self.ramdiskManager.startSynchronizer(syncInterval)
        
        # start the server
        log.info(f"Starting the dedicated server")
        return self.dedicatedServer.startServer()
    
    def waitForEnd(self, checkInterval=5):
        """
        will wait for the server to end, checking every $checkInterval seconds, then it will do the shutdown tasks and return.
        """
        while self.dedicatedServer.isRunning():
            time.sleep(checkInterval)
        return self.stopServer()

    def stopServer(self):
        """
        Will stop the synchronizer, then stop the server and do a last sync from ram 2 mirror
        """
        # stop synchronizer
        self.ramdiskManager.stopSynchronizer()

        if self.dedicatedServer.isRunning():
            # stop server
            self.dedicatedServer.sendExitRetryAndWait()

        # sync ram to mirror
        log.info("Starting final ram to mirror sync after shutdown")
        self.ramdiskManager.syncRamToMirror()

