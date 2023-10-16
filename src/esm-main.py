import time
import logging
from pathlib import Path
from esm import NoSaveGameFoundException, SaveGameMirrorExistsException, UserAbortedException
from esm.EsmMain import EsmMain

log = logging.getLogger(__name__)

def testStartStopServerNoTry():
    log.info("starting server")
    esm.dedicatedServer.startServer()
    log.info("server is running! Will wait 15 secs")
    time.sleep(15)
    log.info("Stopping server again")
    esm.dedicatedServer.sendExitRetryAndWait()
    log.info("Server stopped")

def testStartStopServer():
    try:
        log.info("starting server")
        esm.dedicatedServer.startServer()
        log.info("server is running! Will wait 15 secs")
        time.sleep(15)
    except Exception as ex:
        log.info(f"server didn't start, {ex}")
    
    try:
        log.info("Stopping server again")
        esm.dedicatedServer.sendExitRetryAndWait()
        log.info("Server stopped")
    except Exception as ex:
        log.info(f"Server didnt stop! {ex}")
        try:
            esm.dedicatedServer.killAndWait()
            log.info("Server killed")
        except Exception as ex:
            log.info(f"server couldn't be killed {ex}")

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
            raise UserAbortedException("user decided to abort install")
    except SaveGameMirrorExistsException:
        log.debug("asking user if he wants to delete the existing savegame mirror")        
        if esm.askUserToDeleteOldSavegameMirror():
            log.debug("deleted old savegame mirror")
            testInstall()
        else:
            log.debug("user decided not to delete the old savegame mirror")

def testSetup():
    log.debug("calling setup")          
    esm.ramdiskManager.setup()  

def testStartServerWithSynchronizer():
    log.debug("starting server")
    esm.startServer()
    log.debug("server started, waiting 5 minutes")
    time.sleep(300)
    log.debug("stopping server")
    esm.stopServer()
    log.debug("server stopped")

######################################################
## main code start
######################################################
# initialize config and logging
esm = EsmMain(installDir=Path(".."),
              caller=__file__,
              configFileName="esm/esm-config.yaml"
              )

log.debug("Start of script")
log.debug(f"Logging to: {esm.logFile}")

#testInstall()
#testSetup()
#testStartStopServerNoTry()
#testStartStopServer()
#testStartServerWithSynchronizer()

log.info(f"Script finished successfully. Check the logfile ({esm.logFile}) if you missed something. Bye!")
