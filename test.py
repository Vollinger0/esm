import logging
from esm.EsmMain import EsmMain

esm = EsmMain(caller="test")
log = logging.getLogger(__name__)

log.debug("Start of script")
log.debug(f"Logging to: {esm.logFile}")
log.debug(f"debugging is: {esm.config.general.debugMode}")
