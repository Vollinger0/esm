import logging
import click
from esm.ServiceRegistry import ServiceRegistry
from esm.EsmMain import EsmMain

log = logging.getLogger(__name__)

class LogContext:
    def __enter__(self):
        self.esm = ServiceRegistry.get(EsmMain)
        log.debug("Start of script")
        log.debug(f"Logging to: {self.esm.logFile}")
        log.debug(f"Using config file: {self.esm.configFilePath}")

    def __exit__(self, exc_type, exc_value, traceback):
        log.info(f"Script finished. Check the logfile ({self.esm.logFile}) if you missed something. Bye!")

@click.group()
#@click.option('--config', default="esm-config.yaml", help='configuration file to use', show_default=True)
#@click.option('--log', default="esm", help='logfile name, .log will be appended', show_default=True)
def cli():
    """ 
    Empyrion Server Manager - will help you set up a ramdisk, run the server, do rolling backups and other things efficiently.
    Optimized for speed to be used for busy servers with huge savegames.
    """
    pass

@cli.command(name="prepare-ramdisk", help="Prepares the file system for ramdisk setup")
def ramdiskPrepare():
    """Prepares the file structure to be used with a ramdisk by moving the savegame to the gamesmirror folder. This will also help you create a new savegame if non exists."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.ramdiskPrepare()

@cli.command(name="setup-ramdisk", help="Sets up the ramdisk")
def ramdiskSetup():
    """Sets up the ramdisk - this will actually mount it and copy the hdd mirror to it. Use this after a server reboot before starting the server."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.ramdiskSetup()
    
@cli.command(name="uninstall-ramdisk", help="Reverts the changes done by prepare-ramdisk.")
def ramdiskUninstall():
    """Reverts the changes done by prepare-ramdisk, moving the savegame back to its original location. Use this if you don't want to run the game on a ramdisk any more."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.ramdiskUninstall()

@cli.command(name="start-server", help="Starts up the server")
def startServer():
    """Starts up the server, if ramdisk usage is enabled, this will automatically start the ram2mirror synchronizer task."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.startServer()

@cli.command(name="stop-server", help="Stops the server")
def stopServer():
    """Stops the server, this action will wait for it to end before it returns."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.stopServer()

@cli.command(help="just a test!")
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
