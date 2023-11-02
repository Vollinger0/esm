import importlib
import logging
import signal
import click
from halo import Halo
from esm.Exceptions import ExitCodes, WrongParameterError
from esm.DataTypes import Territory, WipeType
from esm.ServiceRegistry import ServiceRegistry
from esm.EsmMain import EsmMain
from esm.Tools import getElapsedTime, getTimer

log = logging.getLogger(__name__)

class LogContext:
    """context for cli commands to have some basic logging from the start"""
    def __enter__(self):
        self.esm = ServiceRegistry.get(EsmMain)
        log.debug(f"Script started")
        log.debug(f"Logging to: {self.esm.logFile}")
        if self.esm.customConfigFileName:
            log.debug(f"Using base config file: {self.esm.configFilePath} and custom config: {self.esm.customConfigFilePath}")
        else:
            log.debug(f"Using base config file: {self.esm.configFilePath}")

    def __exit__(self, exc_type, exc_value, traceback):
        log.info(f"Script finished. Check the logfile ({self.esm.logFile}) if you missed something. Bye!")

#
# start of cli (click) configuration for the script. see https://click.palletsprojects.com/ for help
#
# this file is the main cli interface and entry point for the script and module.
#
@click.group(epilog='Brought to you by hamster, coffee and pancake symphatisants')
@click.option('-c', '--config', default="esm-custom-config.yaml", metavar='<file>', show_default=True, help="set the custom config file")
@click.option('-v', '--verbose', is_flag=True, help='set loglevel on console to DEBUG')
@click.option('-w', '--wait', is_flag=True, help="if set, will wait and retry to start command, if there is already an instance running. You can set the interval and amount of tries in the configuration.")
def cli(verbose, config, wait):
    """ 
    ESM, the Empyrion Server Manager - will help you set up an optional ramdisk, run the server, do rolling backups, cleanups and other things efficiently.
    Optimized for speed to be used for busy servers with huge savegames.

    Make sure to check the configuration before running any command!

    Tip: You can get more info and options to each command by calling it with the param --help\n
    e.g. "esm tool-wipe-empty-playfields --help"
    """
    if verbose:
        init(streamLogLevel=logging.DEBUG, customConfig=config, wait=wait)
    else:
        init(streamLogLevel=logging.INFO, customConfig=config, wait=wait)


@cli.command(name='version', short_help="shows the scripts version")
def showVersion():
    """ just shows the version of this script"""
    version = importlib.metadata.version(__package__)
    log.info(f"Version is {version}")


@cli.command(name="ramdisk-prepare", short_help="prepares the file system for ramdisk setup")
def ramdiskPrepare():
    """Prepares the file structure to be used with a ramdisk by moving the savegame to the gamesmirror folder. This will also help you create a new savegame if none exists."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        try:
            esm.ramdiskPrepare()
        except Exception as ex:
            log.error(f"Error trying to prepare: {ex}")


@cli.command(name="ramdisk-setup", short_help="sets up the ramdisk")
def ramdiskSetup():
    """Sets up the ramdisk - this will actually mount it and copy the savegame mirror to it. Use this after a server reboot before starting the server.
    This might need admin privileges, so prepare to confirm the elevated privileges prompt from windows.
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.ramdiskSetup()


@cli.command(name="ramdisk-remount", short_help="unmounts the ramdisk and calls ramdisk-setup again to mount it")
def ramdiskRemount():
    """Unmounts the ramdisk and sets it up again. This can be useful if you changed the ramdisk size in the configuration and want to apply those changes.
    This might need admin privileges, so prepare to confirm the elevated privileges prompt from windows.
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.ramdiskRemount()


@cli.command(name="ramdisk-uninstall", short_help="reverts the changes done by ramdisk-prepare.")
@click.option("--force", is_flag=True, default=False, help="force uninstall even if the configuration says to use a ramdisk")
def ramdiskUninstall(force):
    """Reverts the changes done by ramdisk-prepare, moving the savegame back to its original location. Use this if you don't want to run the game on a ramdisk any more.
    This might need admin privileges, so prepare to confirm the elevated privileges prompt from windows.
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        try:
            esm.ramdiskUninstall(force=force)
        except Exception as ex:
            log.error(f"Error trying to uninstall: {ex}")


@cli.command(name="server-start", short_help="starts the server, returns when the server shuts down")
def startServer():
    """Starts up the server, if ramdisk usage is enabled, this will automatically start the ram2mirror synchronizer thread too. The script will return when the server shut down.
    This will *NOT* shut down the server. If you want to do that do that either via other means or use the server-stop command in a new console.
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        start = getTimer()
        with Halo(text="Server running", spinner="dots") as spinner:
            esm.startServerAndWait()
            spinner.succeed("Server shut down")
        log.info(f"Server was running for {getElapsedTime(start)} and has stopped now.")


@cli.command(name="server-stop", short_help="shuts down a running server")
def stopServer():
    """Actively shuts down the server by sending a "saveandexit" command. This action will wait for it to end or until a timeout is reached before it returns"""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        try:
            esm.sendSaveAndExit()
        except TimeoutError as ex:
            log.error(f"Could not stop server. Is it running at all? {ex}")


@cli.command(name="server-resume", short_help="resumes execution of the script if the gameserver is still running")
def resumeServer():
    """Looks for a running server and restarts inner processes accordingly (e.g. the ram synchronizer). Will end when the server shuts down, just like server-start."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        try:
            with Halo(text="Server running", spinner="dots") as spinner:
                esm.resumeServerAndWait()                
                spinner.succeed("Server shut down")
        except TimeoutError as ex:
            log.error(f"Could not resume server. Is it running at all? {ex}")


@cli.command(name="backup-create", short_help="creates a fast rolling backup")
def createBackup():
    """Creates a new rolling mirror backup from the savegame mirror, can be done while the server is running if it is in ramdisk mode."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.createBackup()


@cli.command(name="backup-static-create", short_help="creates a static zipped backup")
def createStaticBackup():
    """Creates a new static and zipped backup of the latest rolling backup. Can be done while the server is running if it is in ramdisk mode."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.createStaticBackup()


@cli.command(name="game-install", short_help="installs the Empyrion Galactic Survival Dedicated Server via steam")
def installGame():
    """Installs the game via steam using the configured paths."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.installGame()


@cli.command(name="game-update", short_help="updates the game via steam and executes additional commands")
def updateGame():
    """Updates the game via steam and executes the additional copy tasks listed in the configuration"""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.updateGame()


@cli.command(name="delete-all", short_help="deletes everything related to the currently configured savegame interactively")
def deleteAll():
    """Deletes the savegame, all the related rolling backups, all eah data, logs and executes all configured delete tasks to be able to start a fresh new savegame.
    This uses delete operations that are optimized for maximum speed and efficiency, which you'll need to delete millions of files.

    Be aware that this will take a lot of time and delete a lot of data if you have a big savegame!
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.deleteAll()


@cli.command(name="tool-wipe-empty-playfields", short_help="wipes empty playfields for a given territory or galaxy-wide")
@click.option('--dblocation', metavar='file', help="location of database file to be used in dry mode. Defaults to use the current savegames DB")
@click.option('--territory', help=f"territory to wipe, use {Territory.GALAXY} for the whole galaxy or any of the configured ones, use --showterritories to get list")
@click.option('--wipetype', help=f"wipe type, one of: {WipeType.valueList()}")
@click.option('--nocleardiscoveredby', is_flag=True, help="If set, will *not* clear the discovered by infos from the wiped playfields")
@click.option('--nodryrun', is_flag=True, help="set to actually execute the wipe on the disk. A custom --dblocation will be ignored!")
@click.option('--showtypes', is_flag=True, help=f"show the supported wipetypes")
@click.option('--showterritories', is_flag=True, help=f"show the configured territories")
def wipeEmptyPlayfields(dblocation, territory, wipetype, nodryrun, showtypes, showterritories, nocleardiscoveredby):
    """Will wipe playfields without players, player owned structures, terrain placeables for a given territory or the whole galaxy.
    This requires the server to be shut down, since it needs access to the current state of the savegame and the filesystem.
    This feature is similar to EAH's "wipe empty playfields" feature, but also considers terrain placeables (which get wiped in EAH).
    This also only takes 60 seconds for a 40GB savegame. EAH needs ~37 hours.
    
    Defaults to use a dryrun, so the results are only written to a csv file for you to check.
    If you use the dry mode just to see how it works, you may aswell define a different savegame database.
    When NOT in dry mode, you can NOT specify a different database to make sure you do not accidentally wipe the wrong playfields folder.
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)  

        if showtypes:
            click.echo("Supported wipe types are:\n" + "\n".join(f"{wt.value.val}\t\t-\t{wt.value.desc}" for wt in list(WipeType)))
            return
        if showterritories:
            click.echo("Configured custom territories:\n" + "\n".join(f"{ct.name}" for ct in esm.wipeService.getAvailableTerritories()))
            click.echo(f"\nUse {Territory.GALAXY} to wipe the whole galaxy.\n")
            return

        if nodryrun and dblocation:
            log.error(f"--nodryrun and --dblocation can not be used together for safety reasons.")
        else:
            try:
                esm.wipeEmptyPlayfields(dbLocation=dblocation, territory=territory, wipeType=wipetype, nodryrun=nodryrun, nocleardiscoveredby=nocleardiscoveredby)
            except WrongParameterError as ex:
                log.error(f"Wrong Parameters: {ex}")


@cli.command(name="tool-purge-empty-playfields", short_help="purges empty playfields that have not been visited for a time")
@click.option('--dblocation', metavar='file', help="location of database file to be used in dry mode. Defaults to use the current savegames DB")
@click.option('--nocleardiscoveredby', is_flag=True, help="If set, will *not* clear the discovered by infos from the purged playfields")
@click.option('--nodryrun', is_flag=True, help="set to actually execute the changes on the disk")
@click.option('--minimumage', default=30, show_default=True, help=f"age a playfield has to have for it to get purged in *days*")
@click.option('--leavetemplates', is_flag=True, help=f"if set, do not delete the related templates")
@click.option('--force', is_flag=True, help=f"if set, do not ask interactively before file deletion")
def purgeEmptyPlayfields(dblocation, nodryrun, nocleardiscoveredby, minimumage, leavetemplates, force):
    """Will *purge* playfields without players, player owned structures, terrain placeables for the whole galaxy.
    This requires the server to be shut down, since it needs access to the current state of the savegame and the filesystem.

    This will actually delete playfields that have not been visited for minimumage days along with the referenced structures 
    and templates from the filesystem (!). Make sure to have a recent backup before doing this.
    
    Defaults to use a dryrun, so the results are only written to a csv file for you to check.
    If you use the dry mode just to see how it works, you may aswell define a different savegame database.
    When NOT in dry mode, you can NOT specify a different database to make sure you do not accidentally purge the wrong playfields folder.
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)  

        if nodryrun and dblocation:
            log.error(f"--nodryrun and --dblocation can not be used together for safety reasons.")
        else:
            try:
                esm.purgeEmptyPlayfields(dbLocation=dblocation, nodryrun=nodryrun, nocleardiscoveredby=nocleardiscoveredby, minimumage=minimumage, leavetemplates=leavetemplates, force=force)
            except WrongParameterError as ex:
                log.error(f"Wrong Parameters: {ex}")


@cli.command(name="tool-purge-wiped-playfields", short_help="purges all playfields that are marked to be completely wiped")
@click.option('--nodryrun', is_flag=True, help="set to actually execute the purge on the disk")
@click.option('--leavetemplates', is_flag=True, help=f"if set, do not delete the related templates")
@click.option('--force', is_flag=True, help=f"if set, do not ask interactively before file deletion")
def purgeWipedPlayfields(nodryrun, leavetemplates, force):
    """Will *purge* all playfields that are marked for complete wipe (with wipetype 'all') including their templates.
    Since this uses the filesystem to check for the info, the execution might take a while on huge savegames.

    This requires the server to be shut down, since it modifies the files on the filesystem.
    Make sure to have a recent backup before doing this!
    
    Defaults to use a dryrun, so the results are only written to a txt file for you to check.
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)  
        try:
            esm.purgeWipedPlayfields(nodryrun=nodryrun, leavetemplates=leavetemplates, force=force)
        except WrongParameterError as ex:
            log.error(f"Wrong Parameters: {ex}")


@cli.command(name="tool-purge-removed-entities", short_help="purges entities that are marked as removed in the database")
@click.option('--dblocation', metavar='file', help="location of database file to be used in dry mode. Defaults to use the current savegames DB")
@click.option('--nodryrun', is_flag=True, help="set to actually execute the purge on the disk")
@click.option('--force', is_flag=True, help=f"if set, do not ask interactively before file deletion")
def purgeRemovedEntities(dblocation, nodryrun, force):
    """Will purge all entities that are marked as removed in the database. This requires the server to be shut down, since it modifies the files on the filesystem.
    
    Defaults to use a dryrun, so the results are only written to a csv file for you to check.
    If you use the dry mode just to see how it works, you may aswell define a different savegame database.
    When NOT in dry mode, you can NOT specify a different database to make sure you do not accidentally purge the wrong playfields folder.
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)  

        if nodryrun and dblocation:
            log.error(f"--nodryrun and --dblocation can not be used together for safety reasons.")
        else:
            try:
                esm.purgeRemovedEntities(dbLocation=dblocation, nodryrun=nodryrun, force=force)
            except WrongParameterError as ex:
                log.error(f"Wrong Parameters: {ex}")


@cli.command(name="tool-cleanup-shared", short_help="removes any obsolete entries in the shared folder")
@click.option('--dblocation', metavar='file', help="location of database file to be used in dry mode. Defaults to use the current savegames DB")
@click.option('--nodryrun', is_flag=True, help="set to actually execute the purge on the disk")
@click.option('--force', is_flag=True, help=f"if set, do not ask interactively before file deletion")
def cleanupShared(dblocation, nodryrun, force):
    """Will check all entries in the Shared-Folder against the database and remove all the ones that shouldn't exist any more or are not needed any more.

    This requires the server to be shut down, since it modifies the files on the filesystem. Make sure to have a recent backup aswell.
    
    Defaults to use a dryrun, so the results are only written to a csv file for you to check.
    If you use the dry mode just to see how it works, you may aswell define a different savegame database.
    When NOT in dry mode, you can NOT specify a different database to make sure you do not accidentally purge the wrong playfields folder.
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)  

        if nodryrun and dblocation:
            log.error(f"--nodryrun and --dblocation can not be used together for safety reasons.")
        else:
            try:
                esm.cleanupSharedFolder(dbLocation=dblocation, nodryrun=nodryrun, force=force)
            except WrongParameterError as ex:
                log.error(f"Wrong Parameters: {ex}")


@cli.command(name="tool-clear-discovered", short_help="clears the discovered info for systems/playields")
@click.option('--dblocation', metavar='file', help="location of database file to be used. Defaults to use the current savegames DB")
@click.option('--nodryrun', is_flag=True, help="set to actually execute the action on the disk")
@click.option('-f', '--file', metavar='file', help="if this is given, use the text file as input for the system/playfield names additionally")
@click.argument('names', nargs=-1)
def clearDiscoveredByInfos(dblocation, nodryrun, file, names):
    """This will clear the discovered-by info from given stars/playfields. Just when you want something to be "Undiscovered" again.
    If you pass a system as parameter, all the playfields in it will be de-discovered.

    Names must be the full names of the playfield, or, if it is a solar system, have the prefix "S:".
    e.g. "S:Alpha", "S:Beta", "Dread", "UCHN Discovery" - etc.

    If you defined a file as input, make sure it is a textfile with *one entry per line*.

    Defaults to use a dryrun, so the results are only written to a csv file for you to check.
    If you use the dry mode just to see how it works, you should probably also define the location of a different database.
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)  
        if not file and not names:
            log.error(f"neither a file nor names were provided, but at least one is required.")
        else:
            try:
                esm.clearDiscoveredByInfos(dbLocation=dblocation, nodryrun=nodryrun, inputFile=file, inputNames=names)
            except WrongParameterError as ex:
                log.error(f"Wrong Parameters: {ex}")


@cli.command(name="terminate-galaxy", short_help="creates a singularity to destroy everything")
@click.option('--i-am-darkestwarrior', is_flag=True, help="forces termination")
@click.option('--i-am-vollinger', is_flag=True, help="graceful shutdown")
@click.option('--i-am-kreliz', is_flag=True, help="have a coffee instead")
def omg(i_am_darkestwarrior, i_am_vollinger, i_am_kreliz):
    """Beware, this function will ^w^w^w
    
    Do not press CTRL+C!
    """
    def NoOp(*args):
        raise KeyboardInterrupt
    with LogContext():
        # reset the global signal handler for this method
        signal.signal(signal.SIGINT, NoOp)

        esm = ServiceRegistry.get(EsmMain)  
        result = ""
        try:
            while result != "yes":
                result = input("Are you really sure? [yes/yes] ")
                if result != "yes": 
                    log.error(f"{result} is not a valid option, try again")
        except:
            log.info(f"It's all your fault now")

        with Halo(text="Destroying worlds", spinner="dots") as spinner:
            try:
                while True:
                    pass
            except KeyboardInterrupt:
                spinner.fail("Stopped")
                log.warning("Destruction of the galaxy ended prematurely. Please contact an expert.")


def init(fileLogLevel=logging.DEBUG, streamLogLevel=logging.INFO, customConfig="esm-custom-config.yaml", wait=False):
    # catch keyboard interrupts 
    signal.signal(signal.SIGINT, forcedExit)
    
    esm = EsmMain(caller="esm",
                configFileName="esm-base-config.yaml",
                customConfigFileName=customConfig,
                fileLogLevel=fileLogLevel,
                streamLogLevel=streamLogLevel
                )
    ServiceRegistry.register(esm)
    
    # enable multiple instance check and wait
    port = esm.config.general.bindingPort
    if wait:
        interval = esm.config.general.multipleInstanceWaitInterval
        tries = esm.config.general.multipleInstanceWaitTries
        esm.openSocket(port, interval=interval, tries=tries)
    else:
        esm.openSocket(port)


def forcedExit(*args):
    log.warning("Script execution interrupted via SIGINT. If the server is still running, you may resume execution via the server-resume command")
    exit(ExitCodes.SCRIPT_INTERRUPTED)

# main cli entry point.
def start():
    cli()
