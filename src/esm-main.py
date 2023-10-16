import os, time
from esm import EsmMain
import logging

log = logging.getLogger()

######################################################
## main code start
######################################################
# initialize config and logging
esm = EsmMain.EsmMain(installDir=os.path.abspath(".."), 
              logFile=os.path.splitext(os.path.basename(__file__))[0] + ".log", 
              configFileName="esm/esm-config.yaml"
              )

log.debug("Start of script")
log.debug(f"Logging to: {esm.logFile}")

try:
    esm.dedicatedServer.startServer()
    log.info("server is running! Will wait 15 secs")
    time.sleep(15)
    log.info("Stopping server again")
    try:
        esm.dedicatedServer.stopAndWait()
        log.info("Server stopped")
    except:
        log.info("Server didnt stop!")
except:
    log.info("server didn't start")
        
log.info(f"Script finished successfully. Check the logfile ({esm.logFile}) if you missed something. Bye!")
