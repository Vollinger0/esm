import os, sys, time
from math import sqrt
from pathlib import Path
import yaml
import sqlite3
import argparse
from esm import EsmMain
import logging

######################################################
## main code start
######################################################
esm = EsmMain(installDir=os.path.abspath(Path(".")), logFile=os.path.splitext(os.path.basename(__file__))[0] + ".log")
log = logging.getLogger()
log.debug("Start of script")
log.debug(f"Logging to: {esm.logFile}")
log.debug(f"Install directory is {esm.installDir}")

esm.dedicatedServer.start()
if esm.dedicatedServer.isRunning():
    log.info("server is running!")
    time.sleep(30)

esm.dedicatedServer.stop()
time.sleep(10)

if esm.dedicatedServer.isRunning():
    log.info("server is still running!")

log.info(f"Script finished successfully. Check the logfile ({esm.logFile}) if you missed something. Bye!")
