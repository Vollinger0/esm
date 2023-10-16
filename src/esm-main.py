from threading import Thread
import time
import logging
from halo import Halo
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
    # with Halo(text='Starting', spinner='dots'):
    esm.startServer()
    log.debug(f"server started")

    # start a separate thread that will send a stop signal to the server after some time.
    def task():
        waittime = 60
        log.debug(f"task started, waiting {waittime} seconds")
        time.sleep(waittime)
        log.debug("task sending exit to server")
        esm.dedicatedServer.sendExit()
        log.debug("task finished ")
    thread = Thread(target=task, daemon=True)
    thread.start()

    # with Halo(text='Waiting', spinner='dots', placement='right'):
    esm.waitForEnd()
    
    #log.debug("waiting for synchronizer to stop")
    #thread.join()
    if esm.dedicatedServer.isRunning():
        log.debug("stopping server")
        # with Halo(text='Stopping', spinner='dots'):
        esm.stopServer()
    log.debug("server stopped")

def test():
    esm.startServer()
    esm.stopServer()

def testBackup():
    esm.createBackup()

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
#test()

log.info(f"Script finished successfully. Check the logfile ({esm.logFile}) if you missed something. Bye!")
