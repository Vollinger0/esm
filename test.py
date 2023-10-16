import logging
from esm.EsmMain import EsmMain
from esm.DataTypes import WipeType

esm = EsmMain(caller="test")
log = logging.getLogger(__name__)

log.debug("Start of script")
log.debug(f"Logging to: {esm.logFile}")
log.debug(f"debugging is: {esm.config.general.debugMode}")

wtl = list(WipeType)

log.debug(f"{wtl}")
foo = list(map(lambda x: x.value.val, wtl))
log.debug(f"{foo}")


