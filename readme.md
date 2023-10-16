## ESM - Empyrion Server Manager



## TODOS:
### done
[x] usecase: start up gameserver
[x] usecase: kill gameserver (via sigterm)

### WIP
[+] usecase: install ramdisk
[+] debugmode
[ ] use pathlib instead of os.path wherever possible

### later
[ ] use the click library to extend the scripts with command line tools
[ ] offer some kind of interactive mode for different stuff
[ ] usecase: server reboot
[ ] usecase: stop gameserver properly
[+] implement regular ram2mirror sync
[+] implement regular mirror2ram sync
[ ] usecase: create incremental backup
[ ] usecase: create manual static backup
[ ] usecase: update gameserver
[ ] usecase: delete savegame
[ ] implement allowMultpleServerInstances switch. Once enabled, do not check for running instances of the game before starting, do not start if startmode is set to direct, etc.
[ ] implement server-callback with epmremoteclient
[ ] implement warning/talkback via tickets
[ ] implement warning/talkback to server chat for syncs, backups probably even random stuff with funny hamster sentences.

### optional
[ ] usecase: create configuration?
[ ] usecase: deinstall ramdisk
[ ] usecase: wipe galaxy
[ ] usecase: purge galaxy
[ ] create separate windows-gui thingy that resides in the taskbar or similar and provides a shortcut to the cli tool.
   ** probably with wxPython
[ ] adapt config to dedicated.yaml, especially when paths change.
