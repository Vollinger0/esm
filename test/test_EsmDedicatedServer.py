import os, sys, time
import logging
import subprocess
import psutil
from pathlib import Path
import unittest
from esm.EsmDedicatedServer import EsmDedicatedServer

class TestEsmDedicatedServer(unittest.TestCase):

    log = logging.getLogger(__name__)

    def test_createLogFileName(self):
        esmDS = EsmDedicatedServer(installDir="..")
        logFileName = esmDS.createLogFileName()
        logFileNameFirst23 = logFileName[:23]
        logFileNameLast4 = logFileName[-4:]
        self.assertEqual("../Logs/4243/Dedicated_", logFileNameFirst23)
        self.assertEqual(".log", logFileNameLast4)
