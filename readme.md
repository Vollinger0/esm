## ESM - Empyrion Server Manager


## releasing:
* execute a $ pip freeze > requirements.txt
** check the computed requirements, clean up as necessary

## TODOS:
### done
[x] usecase: start up gameserver
[x] usecase: kill gameserver (via sigterm)
[x] usecase: install ramdisk
[x] usecase: server reboot
[x] use pathlib instead of os.path wherever possible
[x] implement regular ram2mirror sync
[x] usecase: stop gameserver properly
[x] implement DI
[x] add ram2mirror synchronizer
[x] usecase: create incremental backup
[x] usecase: create manual static backup
[x] tool should check free disk space before doing a new static backup
[x] tool should check free disk space before starting server (especially in ramdisk mode)
[x] usecase: update game
[x] usecase: install game
[x] usecase: delete savegame, including tool data, potential mod data too, add extensions like for the backup
[x] change delete functions so that the path has to be at least 3 levels deep before deleting anything?
[x] change delete functions so that it maintains a list and the user is asked at the end.
[x] usecase: deinstall ramdisk
[x] add proper cli - use the click library to extend the scripts with command line tools
[x] debugmode
[x] split the config in a "basic" config, an custom config that overwrites the basic config.
[x] usecase: wipe galaxy - integrate other script
[x] custom dblocation may not be given in conjunction with nodrymode.
[x] print out wipetypep descriptions on help too.
[x] re-mount option for when ramdisk size has to be updated or ramdisk is down for some reason.
[x] implement server-callback with epmremoteclient

### WIP
[ ] tool: deletes the "discovered by" flags (potentially also for wipes/purges)

### later
[ ] wipes from the wipetool should appear in cb:wipes? Do i need to alter EAHs database too?
[ ] usecase: purge galaxy
[ ] add more epmclient functions, especially the sync event announcements. needs more work from notoats.
[ ] make sure the script only runs once? probably by opening up a port, that way there's no need for cleanups.
[ ] interactive mode for wipe galaxy tool
[+] when useRamdisk is enabled, enable checks for its file structure, when its not, do not start use the synchronizer (of course)
[ ] offer some kind of better interactive mode for different stuff
[ ] implement allowMultpleServerInstances switch. Once enabled, do not check for running instances of the game before starting, do not start if startmode is set to direct, etc.
[ ] implement warning/talkback via tickets
[ ] implement warning/talkback to server chat for syncs, backups probably even random stuff with funny hamster sentences.
[ ] integrity check: checks if things fit together (e.g. dedicated.yaml config), our own config when running multiple instances, etc.
    * or adapt config to dedicated.yaml, especially when paths change. probably as a sanity check implementation
[+] create separate windows-gui thingy that resides in the taskbar or similar and provides a shortcut to the cli tool.

### optional
[-] usecase: create configuration? => probably not needed. the custom config covers our needs.
