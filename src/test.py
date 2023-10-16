from glob import glob
import logging
from pathlib import Path

from esm.EsmMain import EsmMain
from esm.FsTools import FsTools

esm = EsmMain(caller=__file__,
              configFileName="esm-config.yaml"
              )
log = logging.getLogger(__name__)

log.debug("Start of script")
log.debug(f"Logging to: {esm.logFile}")
log.debug(f"debugging is: {esm.config.general.debugMode}")

def testMultipleReturnValues():
    return "Hello", 43, "world"


test1 = testMultipleReturnValues()
test2, test22, test23 = testMultipleReturnValues()

log.debug(f"test1 {test1}")
log.debug(f"test2 {test2}, test22 {test22}, test23 {test23}")

