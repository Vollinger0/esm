# About Performance and the ramdisk

## DETAILS ON RUNNING IN A RAMDISK

#### Performance problems

- egs uses sqlite, which uses a single writer, so almost all game operations require a write on the disk, which is fatal for multiplayer.
- the game creates >>100k directories in single folders (Shared, Playfields, Templates), which end up with several million files for the savegame. This is **extremely** slow on NTFS - a ramdisk speeds this up **considerably**. There's probably nothing that can speed this up more than that.
- the game performance is no longer dependant on the disk io. You can now do admin stuff in the background without affecting the games performance.

#### Things that are sped up:

- access and modifications to inventories/logistics/constructors are instant (-> RW to DB)
- access and modification of the player inventory is instant (-> RW Players folder and DB)
- spawning new entities is instant (-> Shared folder)
- changing terrain on planets is instant (-> Playfields folder)
- adding/modifying/removing blocks from structures are instant (-> Shared folder)
- damaging blocks is instant (greatly improves any kind of fight/battle)

### savegame size and persistence

If you expect your savegame to grow to, e.g. 100GB, i would recommend using a 70GB ramdisk (if you disabled externalizeTemplates, you'll need the full 100GB).
If you restart your OS (and thus, the ramdisk content gets lost), you have to call `esm ramdisk-setup` again. It will re-populate the ramdisk automatically from the mirror - this may take a couple of minutes depending on your hardware and savegame size. I wouldn't recommend restarting my server OS too often, it doesn't help.
You can start out with a smaller ramdisk and increase its size at any time (see `esm ramdisk-remount`). Be aware that you'll have to call `esm ramdisk-setup` every time the ramdisk content gets deleted by a reboot or when you unmount it for some reason.

The ramdisk content is regularly (default=1h) synced back to its HDD mirror in the background (by the ram-synchronizer). This does *not* affect game performance and just takes 1-5 minutes, depending on savegame size. The synchronizer runs only when esm is either running with `esm server-start` or esm operation has resumed with `esm server-resume`.
When the gameserver shuts down, there will be a sync back from ram to hdd mirror *again* after the server ends and before esm finishes, to make sure the hdd mirror is up to date and has a consistent state. This strategy is technically not necessary, but sometimes OSs crash or your hardware may lose power. In the worst case though, you'll lose only 1h of data!
Btw, this is *way* more reliable than without a ramdisk, because an OS crash can very easily cause a corrupted sqlite database, since this file is crucial for the whole savegame.
