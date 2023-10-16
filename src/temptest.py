import os, sys, time
from pathlib import Path
from esm import EsmMain, EsmLogger, EsmDedicatedServer, EsmConfig
import logging
import unittest


######################################################
## main code start
######################################################
esm = EsmMain.EsmMain(installDir=os.path.abspath(Path(".")), logFile=os.path.splitext(os.path.basename(__file__))[0] + ".log")
log = logging.getLogger()
log.debug("Start of script")
log.debug(f"Logging to: {esm.logFile}")
log.debug(f"Working directory is {esm.workingDir}")


config = EsmConfig.EsmConfig("test/test.yaml")


log.info(f"Script finished successfully. Check the logfile ({esm.logFile}) if you missed something. Bye!")
