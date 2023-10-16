import os
import yaml
import logging
from esm import EsmLogger, EsmDedicatedServer, EsmConfig

"""
Main esm class, manages all the other tools, config, etc.
"""
class EsmMain:
    
    logger = logging.getLogger(__name__)

    def __init__(self, installDir=os.path.abspath("."), logFile=os.path.splitext(os.path.basename(__file__))[0] + ".log"):
        self.installDir = installDir
        self.logFile = logFile
        EsmLogger.setUpLogging(logFile)
        self.config = EsmConfig("esm.yaml")
        self.dedicatedServer = EsmDedicatedServer(workingDir=installDir)
