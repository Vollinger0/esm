# About Performance, ramdisk, scenario, shared data and more

## Game server performance

### Problems

- egs uses sqlite, which uses a single writer, so almost all game operations require a write on the disk, which is fatal for multiplayer.
- the game creates >>100k directories in single folders (Shared, Playfields, Templates), which end up with several million files for the savegame. This is **extremely** slow on NTFS. On Windows you don't have many options either.
- creating regular backups of that amount of files takes hours, removing them aswell so your disk may end up being constantly at 100%.

### Solution: **Ramdisk**

- this speeds disk io up to the max, there's probably nothing that can speed this up more than that
- using a ramdisk, the game is no longer dependant on disk io, opening up to do other tasks while the game runs, without affecting it.
- you can now create and delete backups in the background, the game won't even notice.

#### Things that are sped up with a ramdisk

- access and modifications to inventories/logistics/constructors are instant (-> RW to DB)
- access and modification of the player inventory is instant (-> RW Players folder and DB)
- spawning new entities is instant (-> Shared folder)
- changing terrain on planets is instant (-> Playfields folder)
- adding/modifying/removing blocks from structures are instant (-> Shared folder)
- persisting damaging blocks is instant (greatly improves any kind of fight/battle)

#### Savegame size and persistence

If you expect your savegame to grow to, e.g. 50GB, i would recommend using a 35GB ramdisk (if you disabled externalizeTemplates, you'll need the full 50GB).
If you restart your OS (and thus, the ramdisk content gets lost), you have to call `esm ramdisk-setup` again. It will re-populate the ramdisk automatically from the mirror - this may take a couple of minutes depending on your hardware and savegame size. I wouldn't recommend restarting my server OS too often, it doesn't help much.
You can start out with a smaller ramdisk and increase its size at any time (see `esm ramdisk-remount`). Be aware that you'll have to call `esm ramdisk-setup` every time the ramdisk content gets deleted by a reboot or when you unmount it for some reason.

The ramdisk content is regularly synced back to its HDD mirror in the background (default=1h, by the ram-synchronizer). This does *not* affect game performance and just takes 1-5 minutes, depending on savegame size and amount of changes. The synchronizer runs only when esm is either running with `esm server-start` or esm operation has resumed with `esm server-resume`.
When the gameserver shuts down, there will be a sync back from ram to hdd mirror *again* after the server ends and before esm finishes, to make sure the hdd mirror is up to date and has a consistent state. This strategy is technically not necessary, but sometimes OSs crash or your hardware may lose power. In the worst case though, you'll lose only 1h of data!
Btw, this is *way* more reliable than without a ramdisk, because an OS crash can very easily cause a corrupted sqlite database, since this file is crucial for the whole savegame.

#### some timings:

- the synchronizer takes ~1-2 minutes to synchronize two *identical* savegames. Any amount of changes add to that time. Since servers tend to get less populated a while after a fresh wipe, the amount of changes to sync decreases, and the task duration is shorter. On our server it takes ~1-2 minutes for 50 GB (with ~50 players playing in that hour)
- the mirror backups take a bit more time as the synchronizer because they write from disk-to-disk and have to write back changes of 1-2 days (depending on your backup interval and amount). On our server they take about the same 1-2 minutes, due an absolute high-end SSD-Raid. Not that it matters much, since it can run in the background without affecting anything.
- creating static backups (zips) take a lot of time. 90 minutes for a 50GB savegame on the worst but fastest compression. It ends up as a ~20GB zip. You can alter the zip settings in the configuration
- The minimum duration for EAH scheduled restarts is 2,5 minutes due to hardcoded timeouts in EAH. Thanks to the ramdisk, the savegame size is no longer relevant, so the restarts will take just that. The game will be waiting for EAH to time out. Remember to call the async backup script on your restarts.

#### copyright by Vollinger 2023-2024