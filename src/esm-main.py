import os, time
from math import sqrt
from pathlib import Path
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

esm.dedicatedServer.startServer()
if esm.dedicatedServer.isRunning():
    log.info("server is running! Will wait 15 secs")
    time.sleep(15)
    log.info("stopping server again")
    esm.dedicatedServer.stop()

time.sleep(3)
stopped=False
counter=0
while (stopped==False and counter < 20):
    if not esm.dedicatedServer.isRunning():
        stopped=True
    else:
        counter=counter+1
        time.sleep(1)
    
log.info("waited 20 seconds")
if esm.dedicatedServer.isRunning():
    log.info("server is still running!")

log.info(f"Script finished successfully. Check the logfile ({esm.logFile}) if you missed something. Bye!")
