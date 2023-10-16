import logging
import click
from esm.ServiceRegistry import ServiceRegistry
from esm.EsmMain import EsmMain

log = logging.getLogger(__name__)

class LogContext:
    def __enter__(self):
        self.esm = ServiceRegistry.get(EsmMain)
        log.debug(f"Script started")
        log.debug(f"Logging to: {self.esm.logFile}")
        log.debug(f"Using config file: {self.esm.configFilePath}")

    def __exit__(self, exc_type, exc_value, traceback):
        log.info(f"Script finished. Check the logfile ({self.esm.logFile}) if you missed something. Bye!")

@click.group()
#@click.option('--config', default="esm-config.yaml", short_help='configuration file to use', show_default=True)
#@click.option('--log', default="esm", short_help='logfile name, .log will be appended', show_default=True)
def cli():
    """ 
    ESM, the Empyrion Server Manager - will help you set up a ramdisk, run the server, do rolling backups and other things efficiently.
    Optimized for speed to be used for busy servers with huge savegames.
    """
    pass

@cli.command(name="ramdisk-prepare", short_help="prepares the file system for ramdisk setup")
def ramdiskPrepare():
    """Prepares the file structure to be used with a ramdisk by moving the savegame to the gamesmirror folder. This will also help you create a new savegame if non exists."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        try:
            esm.ramdiskPrepare()
        except Exception as ex:
            log.error(f"Error trying to prepare: {ex}")

@cli.command(name="ramdisk-setup", short_help="sets up the ramdisk")
def ramdiskSetup():
    """Sets up the ramdisk - this will actually mount it and copy the hdd mirror to it. Use this after a server reboot before starting the server."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.ramdiskSetup()
    
@cli.command(name="ramdisk-uninstall", short_help="reverts the changes done by ramdisk-prepare.")
@click.option("--force", is_flag=True, default=False, help="force uninstall even if the configuration says to use a ramdisk")
def ramdiskUninstall(force):
    """Reverts the changes done by ramdisk-prepare, moving the savegame back to its original location. Use this if you don't want to run the game on a ramdisk any more."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        try:
            esm.ramdiskUninstall(force=force)
        except Exception as ex:
            log.error(f"Error trying to uninstall: {ex}")

@cli.command(name="server-start", short_help="starts the server")
def startServer():
    """Starts up the server, if ramdisk usage is enabled, this will automatically start the ram2mirror synchronizer task."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.startServer()

@cli.command(name="server-stop", short_help="stops the server")
def stopServer():
    """Stops the server, this action will wait for it to end or until a timeout is reached before it returns"""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        try:
            esm.stopServer()
        except TimeoutError as ex:
            log.error(f"Could not stop server, it is probably not running at all. {ex}")

@cli.command(short_help="just a test!")
def test():
    """long help text """
    with LogContext():    
        log.info("Hi!")

def getEsm():
    return ServiceRegistry.get(EsmMain)

# main cli entry point
def start():
    esm = EsmMain(caller="esm",
                configFileName="esm-config.yaml"
                )
    ServiceRegistry.register(esm)
    cli()
