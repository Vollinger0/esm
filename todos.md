# TODOS

## WIP

- [+] GUI!

## later

- [ ] ask notoats to create a downloadable release of his contained exe, so i can add it as 3rd party requirement
- [ ] provide full installation package with install bat, that installs esm, the tools (osfmount, peazip, emprc, etc.)?
- [ ] implement warning/talkback via tickets for when an admin is required (e.g. low disk space, etc.), e.g. as an extra tool, so it can just be planned in EAH, or as delayed task after a startup (e.g. 5 minutes after the server started)
- [+] fix all FS-modifying tests to use the test fixture of the usually existing ramdisk (R:)
- [ ] offer some kind of better interactive mode for different stuff
  - [-] interactive mode for wipe galaxy tool?
  - [ ] actually make any option have a -batchmode when there are interactive prompts, defaulting to the most defensive option?
- [ ] implement allowMultpleServerInstances switch? Once enabled, do not check for instances of the game before starting, do not start if startmode is set to direct, etc.
- [+] create separate windows-gui thingy that resides in the taskbar or similar and provides a shortcut to the cli tool.
- [ ] fix purge-tools: these need to also delete related data in the database! Probably not difficult to finish implementing, but a PITA to test.

## optional

- [ ] read the territory config from the galaxyconfig.ecf ourselves. Search for "Child Territory" - Blocks.
- [ ] add switch to backup-tool to make backups EWA-compatible
- [ ] provide tool to fix item icons as good as possible in EWA, current process:
   1. open item list in eah, CTRL+A, CTRL+C and copy into text file? Or find out how the item list file in epf got created
   - info from notoats: should be trivial to convert to python
      blocksmap.dat: https://gist.github.com/NotOats/36b6192b4703d55aa5ce334388ff1990
      my old ECF file reader: https://gist.github.com/NotOats/a585298736c70930c89545c4c56aeae9
      just load the item list from ECF files ("BlocksConfig.ecf", "ItemsConfig.ecf") and overwrite with blocksmap.dat entries
   1. read itemid, itemname, devicename from that eah list
   1. find block by matching devicename with blocktype
   1. find customicon name
   1. save customicon as itemid for EWA.
- [ ] add cb:shield:$id function to be able to get a ships shield values?
- [ ] add a AI-powered chatbot, chatgpt-like that roleplays as a spacefaring hamster that reacts to player chat?

## done

- [x] refactor tools, make them wipe instead, or make all tools have the option to additionally purge too? Make it more conscise.
  - [x] tool-wipe (--territory|--file) --wipetype --nocleardiscovered --minimumage
  - [x] tool-clear-discoveredby (--territory|--file) 
  - [-] tool-cleanup-purge-wiped
  - [x] tool-cleanup-shared
  - [x] tool-cleanup-removed-entities
- [-] tool to wipe/purge a list of playfields passed in the command line and/or file?
- [x] refactor configuration once again: put base-config as default-config into the module, and provide an example custom config. The game has to do some sanity checks on startup to make sure the required configurations are in place (like installdir, dedicated yaml, etc.) - Or use something more sophisticated, e.g. a proper getter for config properties that retrieve it from custom -> base -> fallback to a default. => use pydantic!
- [x] check requirements should do a test copy with robocopy
- [x] when useRamdisk is enabled, enable checks for its file structure, when its not, do not start use the synchronizer (of course)
- [-] game-install should have the option to install the scenario? or...
- [x] use pyinstaller to create a distributable program without any installation overhead: <https://pyinstaller.org/>
- [x] update scenario should provide a sync function so that only the real changes are copied, to avoid data-redownloads.
- [x] add more epmclient functions, especially the sync event announcements.
- [x] implement warning/talkback to server chat for syncs, backups probably even random stuff with funny hamster sentences.
- [x] make epmrc client log the return codes properly
- [x] make sure the async-able commands do not check the binding port.
- [x] integrity check: checks if things fit together (e.g. dedicated.yaml config), our own config when running multiple instances, etc.
  - or adapt config to dedicated.yaml, especially when paths change. probably as a sanity check implementation
  - may also just check the config, e.g. if all paths exist
- [x] remove redundant configuration that can be read from the dedicated yaml instead, and do that?
- [x] check for 8dot3name
- [x] update should have the option to disable the steam check?
- [-] usecase: create configuration? => probably not needed. the custom config covers our needs.
- [-] wipes from the wipetool should propagate to EAH? do i need to alter EAHs database too? => no access to eah's dat files.
- [x] make sure the script only runs once? probably by opening up a port, that way there's no need for cleanups.
- [x] create batch file to integrate with EAH
- [x] add versioning and --version option to show it
- [x] make script open up a port to avoid having multiple instances running
- [x] tool to find and delete obsolete folders in Shared
- [x] purge the wiped: check for wipeinfos containing "all", and purge those (fs operations only)
- [x] usecase: purge galaxy
- [x] tool: clean structures that have been removed in the DB, but still exist on the FS (optional also give a min age)
- [x] catch ctrl+c or sigints properly
- [x] server-resume - usecase, for when you have to kill the script and start it again without having to kill the server.
- [x] feature: add the ability to delete the discovered by flag to the wipe tool
- [x] tool: deletes the "discovered by" flags for given systems/playfields (potentially also for wipes/purges)
- [x] add some for spinner or similar when server is running, to see if the console-suspend-bug has hit again
- [x] implement server-callback with epmremoteclient
- [x] re-mount option for when ramdisk size has to be updated or ramdisk is down for some reason.
- [x] print out wipetype descriptions on help too.
- [x] custom dblocation may not be given in conjunction with nodryrun.
- [x] usecase: wipe galaxy - integrate other script
- [x] split the config in a "basic" config, an custom config that overwrites the basic config.
- [x] debugmode
- [x] add proper cli - use the click library to extend the scripts with command line tools
- [x] usecase: deinstall ramdisk
- [x] change delete functions so that it maintains a list and the user is asked at the end.
- [x] change delete functions so that the path has to be at least 3 levels deep before deleting anything?
- [x] usecase: delete savegame, including tool data, potential mod data too, add extensions like for the backup
- [x] usecase: install game
- [x] usecase: update game
- [x] tool should check free disk space before starting server (especially in ramdisk mode)
- [x] tool should check free disk space before doing a new static backup
- [x] usecase: create manual static backup
- [x] usecase: create incremental backup
- [x] add ram2mirror synchronizer
- [x] implement DI
- [x] usecase: stop gameserver properly
- [x] implement regular ram2mirror sync
- [x] use pathlib instead of os.path wherever possible
- [x] usecase: server reboot
- [x] usecase: install ramdisk
- [x] usecase: kill gameserver (via sigterm)
- [x] usecase: start up gameserver

### copyright by Vollinger 2023