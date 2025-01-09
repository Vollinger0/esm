from pathlib import Path
import signal
from threading import Thread
import threading
import time
import logging
from esm.EsmMain import EsmMain
from esm.Tools import getElapsedTime, getTimer
from esm.main import terminateGalaxy, wipeTool

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
    esm.ramdiskInstall()

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
        esm.dedicatedServer.sendExitRetryAndWait()
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

def testClearDiscoveredBy():
    #esm -v tool-clear-discovered --dblocation D:\temp\temp\20230708_original_anvils6_global.db -f namelist_s6.txt
    esm.clearDiscovered(dblocation=r"D:\temp\temp\20230708_original_anvils6_global.db", inputFile="namelist_s6.txt", nodryrun=False)

def testcleanupSharedFolder():
    esm.cleanupSharedFolder()

######################################################
## main code start
######################################################
# initialize config and logging
esm = EsmMain(caller="esm-test", customConfigFilePath=Path("esm-custom-config.yaml"), streamLogLevel=logging.DEBUG)

log.debug(f"Script {__file__} started")
log.debug(f"Logging to: {esm.logFile}")

#esm.wipeTool(dbLocationPath=Path("../20230708_survival_Anvils6_global.db.org").resolve(), nodryrun=False, territoryName="GALAXY", minimumage=30)
#wipeTool(dblocation = "D:\\Servers\\20230708_survival_Anvils6_global.db.org", nodryrun=False, territoryName="GALAXY", minimumage=30)

#terminateGalaxy()
#esm.checkRequirements()
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
#testClearDiscoveredBy()
#testcleanupSharedFolder()
esm.resumeServerAndWait()
#esm.sharedDataServer.start()
#esm.sharedDataServer.resume()
#esm.updateScenario(dryrun=False)
#esm.config.context['logFile'] = Path("./esm-test.log")
#esm.deleteService.backupAllLogs()
#esm.dedicatedServer.assertSharedDataURLIsAvailable()

# def sendSigIntAfter20Secs():
#     time.sleep(20)
#     signal.raise_signal(signal.SIGINT)
# threading.Thread(target=sendSigIntAfter20Secs).start()
#esm.startHaimsterConnectorAndWait()
#esm.exportChatLog()
#esm.resumeServerAndWait()

log.info(f"Script finished successfully. Check the logfile ({esm.logFile}) if you missed something. Bye!")
