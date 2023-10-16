import yaml
import logging

"""
contains all the relevant config for esm, backed by a yaml file.
"""
class EsmConfig:
    
    logger = logging.getLogger(__name__)

    def __init__(self, configPath):
        with open(configPath) as file:
            self.config = yaml.safe_load(file)
    
    def __getattr__(self, name):
        try:
            return EsmConfig(self.config[name])
        except KeyError:
            raise AttributeError(f"'{name}' not found in configuration")

    def __str__(self):
        return str(self.config)
