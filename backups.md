# About backups

The backup system creates a number of rolling backups as mirror copies of the current savegame in a separate folder and creates jointpoints (symlinks) in the original backup folder which point to the rolling backups with a current timestamp as link name. 
When you use this system the *first* few times (depending on configured amount of backups, defaults to 4), it will not be much faster than EAH's backup function, since it has to initially create a full copy of the savegame first. Once all configured rolling backups were created though, all following backups will be blazing fast (e.g. 2 instead of 90 minutes on a 50GB savegame) because only the changes are copied. Using the ramdisk **mirror** as source, it also enables you to create these backups **in the background, while the server is running** - there's no need to shut down the server any more :)

When using the ramdisk, the game is not dependant on the server's disk io any more - which enables you to create rolling backups or static zip backups in the background as you please, since the game's performance will not be affected by that any more nor will any data corrupt due to concurrent file access.

If the ramdisk is disabled, the backup will use the actual savegame as source and require the server to be shut down. It will still be a lot faster than EAH's system though.