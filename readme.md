## ESM - Empyrion Server Manager


## running locally
* install venv: $ py -m venv .venv
* activate venv: $ .\\.venv\Scripts\activate
* install requirements: $ pip install -r requirements.txt
* start esm: $ esm

## releasing:
* execute a $ pip freeze >> requirements.txt
  * check the computed requirements, clean up as necessary
* TODO

## TODOS:
### WIP
- [ ] server-resume - usecase, for when you have to kill the script and start it again without having to kill the server.

### later
- [ ] wipes from the wipetool should propagate to EAH? do i need to alter EAHs database too?
- [ ] usecase: purge galaxy
- [ ] add more epmclient functions, especially the sync event announcements. needs more work from notoats.
- [ ] make sure the script only runs once? probably by opening up a port, that way there's no need for cleanups.
- [ ] offer some kind of better interactive mode for different stuff
  - [ ] interactive mode for wipe galaxy tool?
  - [ ] actually make any option have a -batchmode when there are interactive prompts, defaulting to the most defensive option.
- [+] when useRamdisk is enabled, enable checks for its file structure, when its not, do not start use the synchronizer (of course)
- [ ] implement allowMultpleServerInstances switch. Once enabled, do not check for running instances of the game before starting, do not start if startmode is set to direct, etc.
- [ ] implement warning/talkback via tickets
- [ ] implement warning/talkback to server chat for syncs, backups probably even random stuff with funny hamster sentences.
- [ ] integrity check: checks if things fit together (e.g. dedicated.yaml config), our own config when running multiple instances, etc.
    * or adapt config to dedicated.yaml, especially when paths change. probably as a sanity check implementation
- [+] create separate windows-gui thingy that resides in the taskbar or similar and provides a shortcut to the cli tool.

### optional
- [-] usecase: create configuration? => probably not needed. the custom config covers our needs.

### done
- [x] feature: add the ability to delete the discovered by flag to the wipe tool
- [x] tool: deletes the "discovered by" flags for given systems/playfields (potentially also for wipes/purges)
- [x] add some for spinner or similar when server is running, to see if the console-suspend-bug has hit again
- [x] implement server-callback with epmremoteclient
- [x] re-mount option for when ramdisk size has to be updated or ramdisk is down for some reason.
- [x] print out wipetypep descriptions on help too.
- [x] custom dblocation may not be given in conjunction with nodrymode.
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


#### copyright by Vollinger 2023