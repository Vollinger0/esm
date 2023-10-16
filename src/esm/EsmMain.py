import logging
from pathlib import Path
from halo import Halo
from psutil import TimeoutExpired
from esm import AdminRequiredException, askUser
from esm.EsmFileStructure import EsmFileStructure
from esm.EsmLogger import EsmLogger
from esm.EsmConfig import EsmConfig
from esm.EsmDedicatedServer import EsmDedicatedServer
from esm.EsmRamdiskManager import EsmRamdiskManager

log = logging.getLogger(__name__)

"""
Main esm class, manages all the other tools, config, etc.
"""
class EsmMain:

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
        return EsmFileStructure(self.config)
    
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
        log.info("You'll need to stop it again once you see the button 'Save and Exit' next to the 'Say' button and input field. It takes a bit to appear.")
        if askUser("Ready? [yes/no] ", "yes"):
            log.info("Will start the server with the default configuration now")
            newEsm = EsmDedicatedServer.withGfxMode(self.config, EsmDedicatedServer.GFXMODE_ON)
            try:
                newEsm.startServer()
                # TODO: use the epmclient to check when the server is up and send a saveandexit from there.
                if newEsm.isRunning():
                    log.info("Server is running! Will wait max 600 secs for you to stop it")
                    with Halo(text='Waiting', spinner='dots'):
                        try:
                            newEsm.waitForStop(600)
                        except TimeoutExpired:
                            log.info("Server didn't stop after 600 seconds. Will stop it by force now.")
                            newEsm.killAndWait()
                        except:
                            log.info("Stopping server with force")
                            try:
                                newEsm.killAndWait(15)
                                log.info("Server is gone")
                            except TimeoutExpired:
                                log.info("Server still didnt stop and can not be killed")
                                raise AdminRequiredException("While trying to create a new savegame, the server could not be stopped any more. Please check the process tree and kill it manually.")
                else:
                    log.info("Server didn't start")    
            except:
                log.info("Server didn't start")
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

