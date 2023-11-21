# About backups

The backup system creates a number of rolling backups as mirror copies of the current savegame. They are in a separate folder, jointpoints (symlinks) will be created in the original backup folder which point to the rolling backups with a current timestamp as link name. 

This will look like this:
```
└───Backup
    ├───*20230627 012345 Backup       links to -> BackupMirrors/rollingMirrorBackupX (X changes)
    ├───*20230627 123456 Backup       links to -> BackupMirrors/rollingMirrorBackupX (X changes)
    ├───*20230628 012345 Backup       links to -> BackupMirrors/rollingMirrorBackupX (X changes)
    ├───*20230628 123456 Backup       links to -> BackupMirrors/rollingMirrorBackupX (X changes)
    └───BackupMirrors                 (Folder for the rolling backups, amount of backups depends on config)
        ├───rollingMirrorBackup1
        ├───rollingMirrorBackup2
        ├───rollingMirrorBackup3
        └───rollingMirrorBackup4
```
When you use this system the *first* few times (depending on configured amount of backups, defaults to 4), it will not be much faster than EAH's backup function, since it has to initially create a full copy of the savegame first. Once all configured rolling backups were created though, all following backups will be blazing fast (e.g. 2 instead of 90 minutes on a 50GB savegame) because only the changes are copied. Using the ramdisk **mirror** as source, it also enables you to create these backups **in the background, while the server is running** - there's no need to shut down the server any more.

When using the ramdisk, the game is not dependent on the server's disk io any more - which enables you to create rolling backups or static zip backups in the background as you please, since the game's performance will not be affected by that any more nor will any data corrupt due to concurrent file access.

If the ramdisk is disabled, the backup will use the actual savegame as source and require the server to be shut down. It will still be a lot faster than EAH's system though.