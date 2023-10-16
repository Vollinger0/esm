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

### WIP
[+] debugmode
[ ] usecase: update gameserver

### later
[ ] usecase: delete savegame, including tool data, potential mod data too?
[ ] tool should check free disk space before doing a new static backup
[ ] tool should check free disk space before starting server (especially in ramdisk mode)
[+] when useRamdisk is enabled, enable checks for its file structure, when its not, do not start use the synchronizer (of course)
[ ] use the click library to extend the scripts with command line tools
[ ] offer some kind of better interactive mode for different stuff
[ ] implement allowMultpleServerInstances switch. Once enabled, do not check for running instances of the game before starting, do not start if startmode is set to direct, etc.
[ ] implement server-callback with epmremoteclient
[ ] implement warning/talkback via tickets
[ ] implement warning/talkback to server chat for syncs, backups probably even random stuff with funny hamster sentences.
[ ] integrity check: checks if things fit together (e.g. dedicated.yaml config), our own config when running multiple instances, etc.

### optional
[ ] usecase: create configuration?
[ ] usecase: deinstall ramdisk
[ ] usecase: wipe galaxy
[ ] usecase: purge galaxy, 
[ ] create separate windows-gui thingy that resides in the taskbar or similar and provides a shortcut to the cli tool.
   ** probably with wxPython
[ ] adapt config to dedicated.yaml, especially when paths change. probably as a sanity check implementation
[ ] tool: deletes the "discovered by" flags (potentially also for wipes/purges)
