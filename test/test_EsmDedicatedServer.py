import os, sys, time
import logging
import subprocess
import psutil
from pathlib import Path
import unittest
from esm.EsmDedicatedServer import EsmDedicatedServer
from esm.EsmConfig import EsmConfig

log = logging.getLogger(__name__)

class TestEsmDedicatedServer(unittest.TestCase):

    def test_createLogFileName(self):
        esmConfig = EsmConfig.fromConfigFile('test/esm-test-config.yaml')
        esmDS = EsmDedicatedServer.withConfig(esmConfig)
        logFileName = esmDS.createLogFileName()
        logFileNameFirst23 = logFileName[:23]
        logFileNameLast4 = logFileName[-4:]
        self.assertEqual("../Logs/4243/Dedicated_", logFileNameFirst23)
        self.assertEqual(".log", logFileNameLast4)

    def test_getGfxModeByString(self):
        esmConfig = EsmConfig.fromConfigFile('test/esm-test-config.yaml')
        esmDS = EsmDedicatedServer.withConfig(esmConfig)
        mode = esmDS.getGfxModeByString(True)
        self.assertEqual(mode, EsmDedicatedServer.GFXMODE_ON)
        mode = esmDS.getGfxModeByString(False)
        self.assertEqual(mode, EsmDedicatedServer.GFXMODE_OFF)

    def test_getStartModeByString(self):
        esmConfig = EsmConfig.fromConfigFile('test/esm-test-config.yaml')
        esmDS = EsmDedicatedServer.withConfig(esmConfig)
        mode = esmDS.getStartModeByString('direct')
        self.assertEqual(mode, EsmDedicatedServer.STARTMODE_DIRECT)
        mode = esmDS.getStartModeByString('launcher')
        self.assertEqual(mode, EsmDedicatedServer.STARTMODE_LAUNCHER)

