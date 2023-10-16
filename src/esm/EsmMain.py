import os
import logging
from esm.EsmLogger import EsmLogger
from esm.EsmConfig import EsmConfig
from esm.EsmDedicatedServer import EsmDedicatedServer

log = logging.getLogger(__name__)

"""
Main esm class, manages all the other tools, config, etc.
"""
class EsmMain:

    def __init__(self, logFile, installDir, configFileName):
        self.logFile = logFile
        configFilePath = os.path.abspath(f"{installDir}/{configFileName}")
        self.config = EsmConfig.fromConfigFile(configFilePath)
        EsmLogger.setUpLogging(logFile)
        self.dedicatedServer = EsmDedicatedServer(self.config)
