import logging
from time import sleep
from esm.EsmMain import EsmMain

esm = EsmMain(caller="test")
log = logging.getLogger(__name__)

log.debug("Start of script")
log.debug(f"Logging to: {esm.logFile}")
log.debug(f"debugging is: {esm.config.general.debugMode}")

pfIds = ["1", "4342", 534]

query = "DELETE FROM DiscoveredPlayfields WHERE pfid IN ({})".format(','.join(['?'] * len(pfIds)))

log.debug(f"query: {query}")
