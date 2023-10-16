from pathlib import Path
import time
from esm import EsmMain, NoSaveGameFoundException, SaveGameMirrorExistsException
import logging

log = logging.getLogger()

def testStartStopServer():
    try:
        esm.dedicatedServer.startServer()
        log.info("server is running! Will wait 15 secs")
        time.sleep(15)
        log.info("Stopping server again")
        try:
            esm.dedicatedServer.killAndWait()
            log.info("Server stopped")
        except:
            log.info("Server didnt stop!")
    except:
        log.info("server didn't start")

def testInstall():
    try:
        log.debug("calling install")
        esm.ramdiskManager.install()
    except NoSaveGameFoundException:
        log.debug("asking user to create new savegame")
        if esm.askUserToCreateNewSavegame():
            log.info("calling install again")
            testInstall()
        else:
            log.debug("user decided to abort install")
    except SaveGameMirrorExistsException:
        log.debug("asking user if he wants to delete the existing savegame mirror")        
        if esm.askUserToDeleteOldSavegameMirror():
            log.debug("deleted old savegame mirror")
            testInstall()
        else:
            log.debug("user decided not to delete the old savegame mirror")

######################################################
## main code start
######################################################
# initialize config and logging
esm = EsmMain.EsmMain(installDir=Path(".."),
              caller=__file__,
              configFileName="esm/esm-config.yaml"
              )

log.debug("Start of script")
log.debug(f"Logging to: {esm.logFile}")

#testInstall()
#testStartStopServer()
        
log.info(f"Script finished successfully. Check the logfile ({esm.logFile}) if you missed something. Bye!")
