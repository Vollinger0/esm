from threading import Thread
import time
import logging
from esm.EsmMain import EsmMain
from esm.Tools import getElapsedTime, getTimer

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

def testRamdiskPrepare():
    esm.ramdiskPrepare()

def testRamdiskSetup():
    esm.ramdiskSetup()  

def testRamdiskUninstall():
    esm.ramdiskUninstall(force=True)

def testStartServerWithSynchronizer():
    log.debug("starting server")
    esm.startServer()
    log.debug(f"server started")

    # start a separate thread that will send a stop signal to the server after some time.
    def task():
        waittime = 75
        log.debug(f"task started, waiting {waittime} seconds before trying to stop the server.")
        time.sleep(waittime)
        log.debug("task sending exit to server")
        esm.dedicatedServer.sendExitAndWait()
        log.debug("task finished ")
    thread = Thread(target=task, daemon=True)
    thread.start()

    esm.waitForEnd()
    
    if esm.dedicatedServer.isRunning():
        log.debug("stopping server")
        esm.onShutdown()
    log.debug("server stopped")

def testBackup():
    esm.createBackup()

def testStaticBackup():
    esm.createStaticBackup()    

def testInstallGame():
    esm.installGame()

def testUpdateGame():
    esm.updateGame()

def testDeleteAll():
    esm.deleteAll()

def testStartAndWait():
    start = getTimer()
    esm.startServerAndWait()
    log.info(f"Server shut down after {getElapsedTime(start)}")


######################################################
## main code start
######################################################
# initialize config and logging
esm = EsmMain(caller="esm-test",
              configFileName="esm-config.yaml",
              customConfigFileName="esm-custom-config.yaml",              
              )

log.debug(f"Script {__file__} started")
log.debug(f"Logging to: {esm.logFile}")

#testInstallFromSteam()
#testRamdiskPrepare()
#testRamdiskSetup()
#testRamdiskUninstall()
#testStartStopServerNoTry()
#testStartStopServer()
#testStartServerWithSynchronizer()
#testStartAndWait()
#testUpdateGame()
#testBackup()
#testStaticBackup()
#testDeleteAll()

log.info(f"Script finished successfully. Check the logfile ({esm.logFile}) if you missed something. Bye!")
