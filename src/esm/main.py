import importlib
import logging
import random
import signal
import rich_click as click
import sys
from pathlib import Path
from esm.EsmLogger import EsmLogger
from esm.exceptions import EsmException, ExitCodes, WrongParameterError
from esm.DataTypes import Territory, WipeType
from esm.ServiceRegistry import ServiceRegistry
from esm.EsmMain import EsmMain
from esm.Tools import Timer, getElapsedTime, getTimer

log = logging.getLogger(__name__)

class LogContext:
    """context for cli commands to have some basic logging from the start"""

    def __enter__(self):
        self.esm = ServiceRegistry.get(EsmMain)
        log.debug(f"Script started with params: {sys.argv}")

    def __exit__(self, exc_type, exc_value, traceback):
        # if an EsmException happened, we want to stop the bubble up 
        stopBubbleUp = False
        if exc_type is not None and issubclass(exc_type, EsmException):
            log.error(f"{exc_type.__name__}: {exc_value}")
            stopBubbleUp = True
        log.info(f"Script finished. Check the logfile ('{Path(self.esm.logFile).absolute()}') if you missed something. Bye!")
        return stopBubbleUp


# rich-click configuration for command grouping!
click.rich_click.COMMAND_GROUPS = {
    "esm": [
        {
            "name": "General commands",
            "commands": ["check-requirements", "terminate-galaxy", "version"],
        },
        {
            "name": "Ramdisk commands",
            "commands": ["ramdisk-install", "ramdisk-setup", "ramdisk-remount", "ramdisk-uninstall"],
        },
        {
            "name": "Server commands",
            "commands": ["server-start", "server-resume", "server-stop", "backup-create", "backup-static-create"],
        },
        {
            "name": "Game commands",
            "commands": ["game-install", "game-update", "scenario-update", "delete-all"],
        },
        {
            "name": "Tool commands",
            "commands": [
                "tool-deletecache",
                "tool-wipe", 
                "tool-cleanup-removed-entities", 
                "tool-cleanup-shared", 
                "tool-clear-discovered", 
                "tool-shareddata-server",
                "tool-haimster-connector",
                "tool-export-chatlog",
                "eah-restart",
                "tool-effectiveconfig"
            ],
        },
        {
            "name": "Experimental - use with caution!",
            "commands": [
                "tool-purge-wiped-playfields", 
                "tool-purge-empty-playfields"
            ]
        }
    ]
} 
click.rich_click.STYLE_COMMANDS_TABLE_COLUMN_WIDTH_RATIO = (1, 3)   
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.STYLE_COMMAND = "cyan"
click.rich_click.STYLE_HELPTEXT = ""

#
# start of cli (click) configuration for the script. see https://click.palletsprojects.com/ for help
#
# this file is the main cli interface and entry point for the script and module.
#
@click.group(epilog='Brought to you by hamster, coffee and pancake symphatisants')
@click.option('-c', '--config', default="esm-custom-config.yaml", metavar='<file>', show_default=True, help="set an alternative custom config file.")
@click.option('-v', '--verbose', is_flag=True, help='set loglevel on console to DEBUG. The log file is already set to debug.')
@click.option('-w', '--wait', is_flag=True, help="if set, will wait and retry to start command, if there is already an instance running and you want to run a comand that is limited to one instance only. You can set the interval and amount of retries in the configuration. This option is especially useful for automating tasks")
def cli(verbose, config, wait):
    """ 
    ESM, the Empyrion Server Manager - will help you set up an optional ramdisk, run the server, do rolling backups, cleanups and other things efficiently.\n
    \n
    [green]Optimized for speed to be used for busy servers with huge savegames.[/]\n
    [red bold]Make sure to check the configuration before running any command![/]\n
    \n
    [i]Tip:\n
    You can get more info and options to each command by calling it with the param --help, e.g. "esm tool-wipe --help"\n
    If you use the --verbose flag, you'll probably even see how the script does things![/]\n
    """
    if verbose:
        init(streamLogLevel=logging.DEBUG, customConfig=config, waitForPort=wait)
    else:
        init(streamLogLevel=logging.INFO, customConfig=config, waitForPort=wait)


@cli.command(name='version', short_help="shows this programs version")
def showVersion():
    """really just shows the version of esm"""
    version = getPackageVersion()
    log.info(f"Version is {version}")


@cli.command(name="ramdisk-install", short_help="prepares the file system for ramdisk setup, creates a new savegame if necessary")
def ramdiskInstall():
    """Prepares the file structure to be used with a ramdisk by moving the savegame to the gamesmirror folder. This will also help you create a new savegame if none exists."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.checkAndWaitForOtherInstances()
        esm.ramdiskInstall()


@cli.command(name="ramdisk-setup", short_help="sets up the ramdisk by mounting the ramdisk and copying the existing savegame to it")
def ramdiskSetup():
    """Sets up the ramdisk - this will actually mount it and copy the savegame mirror to it. Use this after a server reboot before starting the server.\n
    \n
    [red bold]This might need admin privileges, so prepare to confirm the elevated privileges prompt from windows.[/]\n
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.checkAndWaitForOtherInstances()
        esm.ramdiskSetup()


@cli.command(name="ramdisk-remount", short_help="unmounts the ramdisk and calls ramdisk-setup to mount it again")
def ramdiskRemount():
    """Unmounts the ramdisk and sets it up again. This can be useful if you changed the ramdisk size in the configuration and want to apply those changes.\n
    \n
    [red bold]This might need admin privileges, so prepare to confirm the elevated privileges prompt from windows.[/]\n
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.checkAndWaitForOtherInstances()
        esm.ramdiskRemount()


@cli.command(name="ramdisk-uninstall", short_help="reverts the changes done by ramdisk-install")
@click.option("--force", is_flag=True, default=False, help="force uninstall even if the configuration says to use a ramdisk")
def ramdiskUninstall(force):
    """Reverts the changes done by ramdisk-install, moving the savegame back to its original location. Use this if you don't want to run the game on a ramdisk any more.\n
    \n
    [red bold]This might need admin privileges, so prepare to confirm the elevated privileges prompt from windows.[/]\n
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.checkAndWaitForOtherInstances()
        esm.ramdiskUninstall(force=force)


@cli.command(name="server-start", short_help="starts the server (included the configured helpers). Returns when the server shuts down")
def startServer():
    """Starts up the server along with all configured esm helpers, like ram synchronizer, haimsterconnector, etc.\n
    \n
    If ramdisk usage is enabled, this will automatically start the ram2mirror synchronizer thread. The script will return when the server shut down.\n
    \n
    If haimster connector is enabled, this will automatically start the haimster connector thread.\n
    \n
    If the shared data tool server is enabled, this will automatically start this aswell\n
    \n
    Stopping this script with CTRL+C will *NOT* shut down the server. If you want to do that do that either via other means or use the server-stop command in a new console.\n
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.checkAndWaitForOtherInstances()
        start = getTimer()
        with EsmLogger.console.status("Server running...") as status:
            esm.startServerAndWait()
            status.stop()
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


@cli.command(name="server-resume", short_help="resumes execution of esm if the gameserver is still running. Will start the additional helpers if required, as described in server-start")
def resumeServer():
    """Looks for a running server and restarts inner helpers accordingly (e.g. the ram synchronizer). Will end when the server shuts down, just like server-start."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.checkAndWaitForOtherInstances()
        try:
            with EsmLogger.console.status("Server running...") as status:
                esm.resumeServerAndWait()
                status.stop()
        except TimeoutError as ex:
            log.error(f"Could not resume server. Is it running at all? {ex}")
            EsmLogger.console.log("Resume failed")


@cli.command(name="backup-create", short_help="creates a fast rolling backup from the savegame mirror")
def createBackup():
    """Creates a new rolling mirror backup of the savegame mirror, can be done while the server is running if it is in ramdisk mode."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.createBackup()


@cli.command(name="backup-static-create", short_help="creates a static zipped backup from the latest rolling backup")
def createStaticBackup():
    """Creates a new static and zipped backup of the latest rolling backup. Can be done while the server is running whether it is running in ramdisk mode or not."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.createStaticBackup()


@cli.command(name="game-install", short_help="installs the Empyrion Galactic Survival Dedicated Server via steam")
def installGame():
    """Installs the game via steam using the configured paths."""
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.checkAndWaitForOtherInstances()
        with Timer() as timer:
            esm.installGame()
        log.info(f"Installation took {timer.elapsedTime} seconds")


@cli.command(name="game-update", short_help="updates and verifies the game via steam and executes additional commands")
@click.option('--nosteam', is_flag=True, help="If set, will *not* update the game via steam, just do the additional tasks")
@click.option('--noadditionals', is_flag=True, help="If set, will *not* do the additional tasks")
def updateGame(nosteam, noadditionals):
    """Updates the game via steam and executes the additional copy tasks listed in the configuration.
    Make sure that neither the game nor EAH are running.\n
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.checkAndWaitForOtherInstances()
        with Timer() as timer:
            esm.updateGame(not nosteam, not noadditionals)
        log.info(f"Update took {timer.elapsedTime} seconds")


@cli.command(name="scenario-update", short_help="updates the configured scenario on the server from the local copy")
@click.option("--source", metavar="<path>", help="path to the scenario source folder to update the scenario from. Overrides the source path in the configuration")
@click.option("--nodryrun", is_flag=True, help="If set, will *not* do a dry run of the update.")
@click.option("--novalidation", is_flag=True, help="If set, will *not* validate scenario files. Use with caution, since broken files might lead to a broken galaxy and savegame.")
def updateScenario(source, nodryrun, novalidation):
    """Updates the scenario on the server using the passed or configured scenario source folder. This will make sure that only files that actually have different content are updated to minimize client downloads.\n
    This tool will also do a basic validation of the scenario before copying it to avoid broken files breaking your galaxy and/or savegame.\n
    \n
    Since steam does not allow for anonymous downloads, you'll need to get the scenario and copy it to the scenario source folder yourself.\n
    Alternatively, you may define the scenario source path with the --source param\n
    \n
    [yellow bold]If you are using the shared data tool, you might want to restart it to recreate the zip after this[/]\n
    \n
    [red bold]The server may not be running for this.[/]\n
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.checkAndWaitForOtherInstances()
        esm.updateScenario(source, not nodryrun, not novalidation)


@cli.command(name="delete-all", short_help="deletes everything related to the currently configured savegame interactively")
@click.option("--doit", is_flag=True, help="must be set to actually do anything.")
def deleteAll(doit):
    """Deletes the savegame, all the related rolling backups, all eah data, logs and executes all configured delete tasks to be able to start a fresh new savegame.\n
    This uses delete operations that are optimized for maximum speed and efficiency, which you'll need to delete millions of files.\n
    \n
    Be aware that this will take a lot of time and delete a lot of data if you have a big savegame!\n
    \n
    [red bold]AGAIN: THIS WILL DELETE ALL SAVEGAME RELATED DATA.[/]\n
    \n
    You may want to use this for starting a new season exclusively, because after this, you will have to.\n
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.checkAndWaitForOtherInstances()
        if not doit:
            raise WrongParameterError("--doit must be set to actually do anything. Didn't you read the help? :p")
        esm.deleteAll()


@cli.command(name="tool-purge-empty-playfields", short_help="purges empty playfields that have not been visited for a time")
@click.option('--dblocation', metavar='file', help="location of database file to be used in dry mode. Defaults to use the current savegames DB")
@click.option('--nocleardiscoveredby', is_flag=True, help="If set, will *not* clear the discovered by infos from the purged playfields")
@click.option('--nodryrun', is_flag=True, help="set to actually execute the changes on the disk")
@click.option('--minimumage', default=30, show_default=True, help=f"age a playfield has to have for it to get purged in *days*")
@click.option('--leavetemplates', is_flag=True, help=f"if set, do not delete the related templates")
@click.option('--force', is_flag=True, help=f"if set, do not ask interactively before file deletion")
def purgeEmptyPlayfieldsOld(dblocation, nodryrun, nocleardiscoveredby, minimumage, leavetemplates, force):
    """Will *purge* playfields without players, player owned structures, terrain placeables for the whole galaxy.
    This requires the server to be shut down, since it needs access to the current state of the savegame and the filesystem.

    This will actually delete playfields that have not been visited for minimumage days along with the referenced structures 
    and templates from the filesystem (!). Make sure to have a recent backup before doing this.
    
    Defaults to use a dryrun, so the results are only written to a csv file for you to check.
    If you use the dry mode just to see how it works, you may aswell define a different savegame database.
    When NOT in dry mode, you can NOT specify a different database to make sure you do not accidentally purge the wrong playfields folder.
    """
    # TODO: this needs to also clean up the related data in the DB, mark entities and structures as deleted, etc.
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)  
        log.warning("EXPERIMENTAL FEATURE!")

        esm.checkAndWaitForOtherInstances()

        if nodryrun and dblocation:
            log.error(f"--nodryrun and --dblocation can not be used together for safety reasons.")
        else:
            esm.purgeEmptyPlayfieldsOld(dbLocation=dblocation, dryrun=not nodryrun, cleardiscoveredby=not nocleardiscoveredby, minimumage=minimumage, leavetemplates=leavetemplates, force=force)


@cli.command(name="tool-purge-wiped-playfields", short_help="purges all playfields that are marked to be completely wiped")
@click.option('--nodryrun', is_flag=True, help="set to actually execute the purge on the disk")
@click.option('--leavetemplates', is_flag=True, help=f"if set, do not delete the related templates")
@click.option('--force', is_flag=True, help=f"if set, do not ask interactively before file deletion")
def purgeWipedPlayfieldsOld(nodryrun, leavetemplates, force):
    """Will *purge* all playfields that are marked for complete wipe (with wipetype 'all') including their templates.
    Since this uses the filesystem to check for the info, the execution might take a while on huge savegames.

    This requires the server to be shut down, since it modifies the files on the filesystem.
    Make sure to have a recent backup before doing this!
    
    Defaults to use a dryrun, so the results are only written to a txt file for you to check.
    """
    # TODO: this needs to also clean up the related data in the DB, mark entities and structures as deleted, etc.
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)  
        log.warning("EXPERIMENTAL FEATURE!")

        esm.checkAndWaitForOtherInstances()
        esm.purgeWipedPlayfieldsOld(dryrun=not nodryrun, leavetemplates=leavetemplates, force=force)


@cli.command(name="tool-cleanup-removed-entities", short_help="delete obsolete entity files that are marked as removed in the database")
@click.option('--savegame', metavar='<path>', help="location of savegame to use, e.g. to use this on a different savegame or savegame copy") 
@click.option('--nodryrun', is_flag=True, help="set to actually execute the purge on the disk")
@click.option('--force', is_flag=True, help=f"if set, do not ask interactively before file deletion, use with caution")
def toolCleanupRemovedEntities(savegame, nodryrun, force):
    """Will delete all related files to all entities that are marked as removed in the database interactively.\n
    \n
    If --savegame is the current savegame, this requires the server to be shut down, since it modifies the files on the filesystem. Make sure to have a recent backup aswell.\n
    \n
    Defaults to use a dryrun, so the results are only written to a csv file for you to check.\n
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)  
        esm.cleanupRemovedEntities(savegame=savegame, dryrun=not nodryrun, force=force)


@cli.command(name="tool-cleanup-shared", short_help="removes any obsolete files in the Shared folder")
@click.option('--savegame', metavar='<path>', help="location of savegame to use, e.g. to use this on a different savegame or savegame copy") 
@click.option('--nodryrun', is_flag=True, help="set to actually execute the purge on the disk")
@click.option('--force', is_flag=True, help=f"if set, do not ask interactively before file deletion, use with caution")
def toolCleanupShared(savegame, nodryrun, force):
    """Will check all entries in the Shared-Folder against the database and remove all the ones that shouldn't exist any more since there is no more related data in the database.\n
    \n
    If --savegame is the current savegame, this requires the server to be shut down, since it modifies the files on the filesystem. Make sure to have a recent backup aswell.\n
    \n
    Defaults to use a dryrun, so the results are only written to a csv file for you to check.\n
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)  
        esm.cleanupSharedFolder(savegame=savegame, dryrun=not nodryrun, force=force)


@cli.command(name="tool-clear-discovered", short_help="clears the discovered-by info for systems/playields")
@click.option('--territory', metavar='<territory>', type=str, help=f"territory where to clear the discovered-by info. Use {Territory.GALAXY} for the whole galaxy or any of the configured ones, use --showterritories to get the list")
@click.option('--showterritories', is_flag=True, help="show the configured territories and exit")
@click.option('--listfile', metavar='<file>', help="if this is given, use the text file as input for the system/playfield names additionally to the names passed as argument. The list file has to contain an entry per line, see the help of names for the syntax")
@click.option('--nodryrun', is_flag=True, help="set to actually execute the action on the disk")
@click.option('--dblocation', metavar='<file>', help="location of database file to be used. Defaults to use the current savegames database")
@click.argument('names', nargs=-1)
def toolClearDiscovered(dblocation, nodryrun, territory, showterritories, listfile, names):
    """This will clear the discovered-by info from given stars/playfields. Just when you want something to be "Undiscovered" again.\n
    \n    
    If you pass a system as parameter, all the playfields in it will be de-discovered.\n
    \n
    Names must be the full names of the playfield, or, if it is a solar system, have the prefix [yellow]S:[/].\n
    e.g. [yellow]S:Alpha[/], [yellow]S:Beta[/], [yellow]Dread[/], [yellow]UCHN Discovery[/] - etc.\n
    \n
    If you defined a file as input, make sure it is a textfile with *one entry per line*.\n
    \n
    If you pass a territory, all the stars in that territory will be de-discovered. You can not combine --territory with --files or the names as argument.\n
    \n        
    Defaults to use a dryrun, so the results are only written to a csv file for you to check.\n
    If you use the dry mode just to see how it works, you should probably also define the location of a different database.\n
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)  
        esm.checkAndWaitForOtherInstances()

        if showterritories:
            showConfiguredTerritories(esm)
            return

        if territory and listfile:
            raise WrongParameterError(f"--territory and --listfile can not be combined.")

        if territory and names:
            raise WrongParameterError(f"--territory and names can not be combined.")

        if not listfile and not names and not territory:
            raise WrongParameterError(f"neither a file nor names nor territory were provided, but at least one is required.")

        if territory:
            checkTerritoryParameter(territory, esm)
        
        esm.clearDiscovered(dblocation=dblocation, dryrun=not nodryrun, territoryName=territory, inputFile=listfile, inputNames=names)


@cli.command(name="tool-export-chatlog", short_help="exports the chatlog of a game to a file")
@click.option('--dblocation', metavar='<file>', help="location of database file to be used. Defaults to use the current savegames database")
@click.option('--filename', metavar='<path>', default="chatlog.json", show_default=True, help="the filename to write the chatlog to. The extension will be adjusted according to the file format specified")
@click.option('--format', default="json", type=click.Choice(["json","text"]), show_default=True, help=f"the format to use for the export")
@click.option('--excludenames', '-e', multiple=True, type=str, help="a list of sender names to exclude from the chatlog")
@click.option('--includenames', '-i', multiple=True, type=str, help="a list of sender names to include from the chatlog")
def toolExportChatlog(dblocation, filename, format, excludenames, includenames):
    """
        Exports the chat log for current or given database to a the file system, with the specified filename and format\n
        \n
        --includenames and --excludenames mutually exclusive and case sensitive\n
        You can pass a list of names like this: -e "name1" -e "name2" etc.\n
        \n
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        if len(excludenames) > 0 and len(includenames) > 0:
            raise WrongParameterError(f"Either --excludenames or --includenames can be used, but not both at the same time.")
        esm.exportChatLog(dblocation=dblocation, filename=filename, format=format, excludeNames=list(excludenames), includeNames=list(includenames))


@cli.command(name="tool-shareddata-server", short_help="starts a webserver to serve the shared data as a downloadable zip, if you do not want it to start with the main server.")
@click.option('--resume', is_flag=True, help="if set, just resume the server, do not recreate data or change the configuration.")
@click.option('--force-recreate', default=False, is_flag=True, show_default=True, help="if set, will force recreation of the zip files even if esm finds out that it is not necessary")
def toolSharedDataServer(resume, force_recreate):
    """This will start a webserver to serve the shared data of the configured scenario as a downloadable zip.\n
    \n    
    The tool will check the shared data folder in the scenario and recreate the zip if needed. It will not if you use resume. The server will provide instructions at (/)\n 
    and the download at the configured path.\n
    Make sure to enable the "useSharedDataURLFeature" property in the configuration, if you want to use that feature with it.\n
    This can be started completely separate from the main server and will run in the background until you stop it via CTRL+C.\n
    \n
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.setUpLogging(caller="esm-shareddata-server", streamLogLevel=EsmLogger.streamLogLevel, fileLogLevel=EsmLogger.fileLogLevel)
        with Timer() as timer:
            with EsmLogger.console.status("Server running...") as status:
                esm.startSharedDataServer(resume, force_recreate, wait=True)
            status.stop()
        log.info(f"Server was running for {timer.elapsedTime} and has stopped now.")

@cli.command(name="tool-haimster-connector", short_help="starts the haimster connector as separate tool")
def toolHaimsterConnector():
    """This will start the haimster connector that will connect haimster with the games chat.\n
    \n
    Obviously, this tool start ignores the toggle for the haimster integration in the configuration settings.
    This can be started completely separate from the main server and will run in the background until you stop it via CTRL+C.\n
    
    Of course, this requires the server and haimster to be running, so you need to start them first.\n

    Be aware that, if the server shuts down or is otherwise unreachable, the tool will keep trying to communicate and may fail eventually.\n
    \n
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.setUpLogging(caller="esm-haimster-connector", streamLogLevel=EsmLogger.streamLogLevel, fileLogLevel=EsmLogger.fileLogLevel)
        with Timer() as timer:
            with EsmLogger.console.status("Server running...") as status:
                esm.startHaimsterConnectorAndWait()
            status.stop()
        log.info(f"Server was running for {timer.elapsedTime} and has stopped now.")


@cli.command(name="terminate-galaxy", short_help="creates a singularity to destroy everything")
@click.option('--i-am-darkestwarrior', is_flag=True, help="forces termination with an evil laugh")
@click.option('--i-am-vollinger', is_flag=True, help="quick and graceful shutdown")
@click.option('--i-am-kreliz', is_flag=True, help="have some pancackes and a coffee instead")
@click.option('--who-is-kr0n', is_flag=True, help="do not... oh look, a squirrel!")
def terminateGalaxy(i_am_darkestwarrior, i_am_vollinger, i_am_kreliz, who_is_kr0n):
    """Beware, this function will ^w^w^w\n
    \n    
    Do not press CTRL+C!\n
    """
    def NoOp(*args):
        raise KeyboardInterrupt()
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
            culprit = None
            for key, value in locals().items():
                if key.startswith("i_am_"):
                    if value:
                        culprit = key[len("i_am_"):]
            if culprit:
                click.echo("It's all your fault now " + click.style(culprit, fg="red"))
            else:
                culprit = random.choice([key for key in locals() if key.startswith("i_am_")])
                click.echo("It's all " + click.style(culprit[len("i_am_"):], fg="red") + "'s fault")

        try:
            esm.openSocket(raiseException=True)
            with EsmLogger.console.status("Destroying worlds...") as status:
                try:
                    while True:
                        pass
                except KeyboardInterrupt:
                    status.stop()
                    log.warning("Destruction of the galaxy ended prematurely. Please contact an expert.")
        except:
            log.error("Looks like someone else is already destroying the world!")


@cli.command(name="check-requirements", short_help="checks various configs and requirements")
@click.option('--nonadmin', is_flag=True, help="skip checks that require admin privileges")
def checkRequirements(nonadmin):
    """Will do several checks, including:\n
    \n
    \b\n
    - if 8dot3name generation is enabled on the game drive\n
    - if hardlinks are supported on the drives filesystem\n
    - configuration of various paths to tools\n
    - elevated privileges for accessing ramdisks\n
    - free disk space on install dir and savegame dir\n
    - other things\n
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.checkRequirements(not nonadmin)


@cli.command(name="tool-effectiveconfig", short_help="saves the effective configuration based on the default config file as a new file")
@click.option('--configfile', default="esm-effective-config.yaml", metavar='<file>', help="the config file to save the effective config file to")
@click.option('--overwrite', default=False, is_flag=True, help="if the file already exists, overwrite it")
def toolEfectiveConfig(configfile, overwrite):
    """Will save the effective config based on the default config file as a new file.
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.saveEffectiveConfig(configfile, overwrite)


@cli.command(name="eah-restart", short_help="restarts (or stops) EAH using its import-commands feature. Will only work if its running, of course.")
@click.option('--eahpath', metavar='<path>', help="optional path to alternative eah installation, if you are not using the one provided by the game")
@click.option('--stop', default=False, show_default=True, is_flag=True, help="if set, will stop eah instead of just restarting it. Beware that this tool can not start eah")
@click.option('--delay', default=60, show_default=True, help="time to wait until triggering the command. This is helpful so EAH has time to finish the call to esm properly.")
def triggerEahRestart(eahpath, stop, delay):
    """
        Restarts or stops EAH using its import-commands feature. Will only work if its running, of course.
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.triggerEahRestart(eahpath, stop, delay)


@cli.command(name="tool-deletecache", short_help="deletes the ever growing cache. This can be safely done every now and then, since the cache grow to hundreds of GBs.")
@click.option('--noconfirm', is_flag=True, default=False, help="set to have the tool delete without asking you first - use with care!")
def deleteGameCache(noconfirm):
    """
        Deletes the ever growing cache. This can be safely done every now and then, since the cache grow to hundreds of GBs - the server must be stopped first.
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)
        esm.checkAndWaitForOtherInstances()
        esm.deleteGameCache(not noconfirm)


@cli.command(name="tool-wipe", short_help="provides a lot of options to wipe empty playfields, check the help for details", no_args_is_help=True)
@click.option('--listfile', metavar='<file>', help="if this is given, use the text file as input for the system/playfield names. Syntax: <S:Systemname> for systems, <Playfield> for playfields. The textfile has to be a simple list with one string per line containing either a system or a playfield name with no quotes or special characters.")
@click.option('--territory', metavar='<territory>', type=str, help=f"territory to wipe, use {Territory.GALAXY} for the whole galaxy or any of the configured ones, use --showterritories to get the list")
@click.option('--showterritories', is_flag=True, help="show the configured territories. This will read them from the scenario GalaxyConfig and add the ones from the esm configuration.")

@click.option('--wipetype', type=str, metavar="<wipetype>", help="what type of wipe to apply to the playfields, use --showtypes to get the list of available types")
@click.option('--showtypes', is_flag=True, help="show the supported wipetypes the game supports")

@click.option('--nocleardiscoveredby', is_flag=True, help="if set, will *not* clear the discovered-by infos from the wiped/purged playfields")
@click.option('--minage', type=int, help="the playfields will only be wiped/purged if they have not been visited for the specified amount of days.")

@click.option('--dblocation', metavar='<file>', help="location of database file to be used in dry mode. Defaults to use the current savegames DB")
@click.option('--nodryrun', is_flag=True, help="set to actually execute the changes on the disk")
def wipeTool(listfile, territory, showterritories, wipetype, showtypes, nocleardiscoveredby, minage, dblocation, nodryrun):
    """This tool will *wipe* playfields as specified but will not touch any playfield with players, player owned structures or terrain placeables.\n
    This feature is similar to EAH's "wipe empty playfields" feature, but also considers terrain placeables (which get wiped in EAH).\n
    This also only takes 60 seconds for a 40GB savegame. EAH needs ~37 hours.\n
    \n
    This requires the server to be shut down, since it needs access to the current state of the savegame and the filesystem.\n
    \n
    You can not combine --listfile with --territory\n
    You can not combine --dblocation and --nodryrun. This is to make sure you do not accidentally purge the wrong playfields folder.\n
    \n
    Defaults to use a dryrun, so the results are only written to a csv file for you to check.\n
    If you use the dry mode just to see how it works, you may aswell define a different savegame database,\n
    e.g. from a backup.\n
    \n
    Tip: use dblocation and dryrun to test your action on a backup a few times before executing it on the live savegame.\n
    """
    with LogContext():
        esm = ServiceRegistry.get(EsmMain)  
        if showtypes:
            showWipeTypes()
            return
        
        if showterritories:
            showConfiguredTerritories(esm)
            return

        if listfile and territory:
            raise WrongParameterError(f"--listfile and --territory can not be used together")
        
        if not wipetype:
            raise WrongParameterError(f"--wipetype must be set")
        
        if nodryrun and dblocation:
            raise WrongParameterError(f"--nodryrun and --dblocation can not be used together for safety reasons")
        
        if not listfile and not territory:
            raise WrongParameterError(f"Either --listfile or --territory must be used")

        inputFilePath = None
        if not listfile:
            checkTerritoryParameter(territory, esm)
        else:
            inputFilePath = Path(listfile)
            if not inputFilePath.exists():
                raise WrongParameterError(f"file {inputFilePath} does not exist.")

        checkWipeTypeParameter(wipetype)
            
        if minage:
            minage = int(minage)
            if minage < 0:
                raise WrongParameterError(f"minage must be >= 0")
        
        if nodryrun:
            esm.checkAndWaitForOtherInstances()

        esm.wipeTool(inputFilePath=inputFilePath, territoryName=territory, wipetype=WipeType.byName(wipetype), cleardiscoveredby=not nocleardiscoveredby, minage=minage, dbLocation=dblocation, dryrun=not nodryrun)

def showConfiguredTerritories(esm: EsmMain):
    """
        just print out the configured custom territories as a table
    """
    territoryList = []
    for territory in esm.configService.getAvailableTerritories():
        name = territory.name
        centerx = territory.x/100000
        centery = territory.y/100000
        centerz = territory.z/100000
        radius = territory.radius/100000
        territoryList.append(f"{name:<40}\t{centerx:>10}\t{centery:>10}\t{centerz:>10}\t{radius:>10}")

    click.echo(f"Configured custom territories:\n" + 
               f"{"Territory name":<40}\t{"center x":>10}\t{"center y":>10}\t{"center z":>10}\t{"radius":>10}\n" +
               f"----------------------------------------------------------------------------------------------------------\n" +
               f"\n".join(territoryList))
    click.echo(f"\nUse the name '{Territory.GALAXY}' to wipe the whole galaxy.\n")


def showWipeTypes():
    """
        just print out the supported wipe types
    """
    click.echo("Supported wipe types are:\n\n" + "\n".join(f"{wt.value.name}\t\t-\t{wt.value.description}" for wt in list(WipeType))+"\n")

def checkWipeTypeParameter(wipetype):
    wtl = WipeType.valueList()
    if wipetype and wipetype in wtl:
        log.debug(f"valid wipetype selected '{wipetype}'")
    else:
        raise WrongParameterError(f"Wipe type '{wipetype}' not valid, must be one of: {wtl}")

def checkTerritoryParameter(territory, esm: EsmMain):
    availableTerritories = esm.configService.getAvailableTerritories()
    atn = list(map(lambda x: x.name, availableTerritories))
    if territory and (territory in atn or territory == Territory.GALAXY):
        log.debug(f"valid territory selected '{territory}'")
    else:
        raise WrongParameterError(f"Territory '{territory}' not valid, must be one of: {Territory.GALAXY}, {', '.join(atn)}")

def getPackageVersion():
    return importlib.metadata.version(__package__)

def init(fileLogLevel=logging.DEBUG, streamLogLevel=logging.INFO, waitForPort=False, customConfig=None):
    # catch keyboard interrupts 
    signal.signal(signal.SIGINT, forcedExit)
    
    esm = EsmMain(caller="esm",
                fileLogLevel=fileLogLevel,
                streamLogLevel=streamLogLevel,
                waitForPort=waitForPort,
                customConfigFilePath=Path(customConfig)
                )
    ServiceRegistry.register(esm)
    
def forcedExit(*args):
    log.warning("Script execution interrupted via SIGINT. Stopping esm services...")
    esm = ServiceRegistry.get(EsmMain)
    esm.stop()
    log.warning("Script execution interrupted via SIGINT. ESM services stopped, if the server is still running, you may resume execution via the server-resume command")
    sys.exit(ExitCodes.SCRIPT_INTERRUPTED)

# main cli entry point.
def start():
    # wrap *all* exceptions so they end up in the log at least. Anything that bubbled up to here is probably a bug. 
    # all other exceptions we caused ourselves should be a subtype of EsmException
    try:
        cli()
    except Exception as ex:
        log.error(ex, exc_info=True)
        raise ex
