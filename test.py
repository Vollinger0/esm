import logging
from esm.EsmConfigService import EsmConfigService
from esm.EsmMain import EsmMain

esm = EsmMain(caller="test")
log = logging.getLogger(__name__)

log.debug("Start of script")
log.debug(f"Logging to: {esm.logFile}")
log.debug(f"debugging is: {esm.config.general.debugMode}")


configFilePath="test/esm-test-config.yaml"
config = EsmConfigService(configFilePath=configFilePath)

