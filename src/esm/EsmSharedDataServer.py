from functools import cached_property
import logging
from esm.ConfigModels import MainConfig
from esm.EsmConfigService import EsmConfigService
from esm.ServiceRegistry import Service, ServiceRegistry

log = logging.getLogger(__name__)

@Service
class EsmSharedDataServer:

    @cached_property
    def config(self) -> MainConfig:
        return ServiceRegistry.get(EsmConfigService).config

    def start(self):
        # TODO: create zip from the shared data folder with the configured folder name
        # TODO: start webserver on configured port and serve the zip, maybe also with a dynamic index.html that explains how to handle the shared data
        # TODO: log that the server is running and when someone downloads the zip
        log.info("would have started the download server now, but its not implemented yet")
        pass