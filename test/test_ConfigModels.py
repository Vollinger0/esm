import logging
import unittest
from pathlib import Path
from pydantic import ValidationError
from easyconfig import create_app_config

import yaml

log = logging.getLogger(__name__)

class test_ConfigModels(unittest.TestCase):

    REQUIRED_MODEL = {'server': {'dedicatedYaml': "foo.yaml"}, "paths": {"install": "R:\doodoo"}}
    
    def test_canCreateConfigModel(self):
        from esm.ConfigModels import MainConfig
        config = MainConfig.model_validate(test_ConfigModels.REQUIRED_MODEL)

    def test_canCreateConfigModelEasyConfigWay(self):
        from esm.ConfigModels import MainConfig
        config = MainConfig(server={'dedicatedYaml': "foo.yaml"}, paths={"install": "R:\foofoo"})

    def test_CorrectConfigLoads(self):
        from esm.ConfigModels import MainConfig
        configFilePath = Path("test/test-correct-config.yaml")
        with open(configFilePath, "r") as configFile:
            configContent = yaml.safe_load(configFile)
            config = MainConfig.model_validate(configContent)
            self.assertEqual(config.server.dedicatedYaml, Path("esm-correct.yaml"))

    def test_CorrectConfigLoadsNew(self):
        from esm.ConfigModels import MainConfig
        configFilePath = Path("test/test-correct-config.yaml")
        model = MainConfig.model_validate(test_ConfigModels.REQUIRED_MODEL, strict=False)
        config = create_app_config(model)
        config.load_config_file(configFilePath)
        self.assertEqual(config.server.dedicatedYaml, Path("esm-correct.yaml"))

    def test_WrongConfigThrowsError(self):
        from esm.ConfigModels import MainConfig
        configFilePath = Path("test/test-incorrect-config.yaml")
        with open(configFilePath, "r") as configFile:
            configContent = yaml.safe_load(configFile)
            with self.assertRaises(ValidationError):
                config = MainConfig.model_validate(configContent)

    def test_MissingconfigGeneratesExample(self):
        configFilePath = Path("test/test-generated-config.yaml")
        if configFilePath.exists(): configFilePath.unlink()

        from esm.ConfigModels import MainConfig

        newModel = MainConfig.model_validate(test_ConfigModels.REQUIRED_MODEL)
        config = create_app_config(newModel)
        config.load_config_file(configFilePath)

        with open(configFilePath, "r") as configFile:
            configContent = yaml.safe_load(configFile)
            config = MainConfig.model_validate(configContent)
            self.assertTrue(configFilePath.exists())
            self.assertTrue(configFilePath.stat().st_size>1000)
            self.assertEqual(config.server.dedicatedYaml, Path("foo.yaml"))

    def test_ConfigRamdiskPatterns(self):
        from esm.ConfigModels import ConfigRamdisk
        rdconfig = ConfigRamdisk()
        self.assertEqual(rdconfig.drive, "R:")
        self.assertEqual(rdconfig.size, "2G")
        self.assertEqual(rdconfig.synchronizeRamToMirrorInterval, 3600)
        rdconfig = ConfigRamdisk(drive="X:")
        self.assertEqual(rdconfig.drive, "X:")
        with self.assertRaises(ValidationError):
            rdconfig = ConfigRamdisk(drive="yy")
        rdconfig = ConfigRamdisk(size="1k")
        self.assertEqual(rdconfig.size, "1k")
        rdconfig = ConfigRamdisk(size="2.5M")
        self.assertEqual(rdconfig.size, "2.5M")
        rdconfig = ConfigRamdisk(size="3.34345G")
        self.assertEqual(rdconfig.size, "3.34345G")
        with self.assertRaises(ValidationError):
            rdconfig = ConfigRamdisk(size="3.3434ff5G")

    def test_ConfigGeneral(self):
        from esm.ConfigModels import ConfigGeneral
        generalConfig = ConfigGeneral()
        self.assertEqual(generalConfig.bindingPort, 6969)
        with self.assertRaises(ValidationError):
            generalConfig = ConfigGeneral(bindingPort=1023)
        with self.assertRaises(ValidationError):
            generalConfig = ConfigGeneral(bindingPort=65536)

    def test_OverwritingConfig(self):
        from esm.ConfigModels import MainConfig
        configFilePath = Path("test/test-overwriting-config.yaml")
        with open(configFilePath, "r") as configFile:
            configContent = yaml.safe_load(configFile)
            config = MainConfig.model_validate(configContent)
            # check overwritten values
            self.assertEqual(config.server.dedicatedYaml, Path("esm-overwritten.yaml"))
            self.assertEqual(config.general.bindingPort, 7069)
            self.assertEqual(Path(config.updates.scenariosource), Path("D:\Servers\Scenarios"))

            # check default values
            self.assertEqual(config.ramdisk.drive, "R:")
            self.assertEqual(config.backups.amount, 4)
