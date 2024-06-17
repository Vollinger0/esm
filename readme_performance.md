# About Performance, ramdisk, shared data downloads and more

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

## About scenarios and shared data downloads

The games network bandwith seems to be limited to ~10MB/s for the whole server. This bandwith has to be shared by all players currently playing and all players who want to download anything. If you have big scenario updates, prepare to have network issues for the rest of the day. Unless, of course, you use the shared data server tool (see below).

### Things to consider
The game does not check for content changes on the SharedData-files of the scenario. It only checks for the last modification date of these files. Once that changes, a re-download is triggered for the client. If you touch all the files in the shared folder, the clients will redownload the whole scenario although nothing really changed.
The `esm scenario-update` command will make sure this does not happen and will update the game scenario files only, if their content really changed, minimizing the need for everyone to redownload things.

### The Shared Data Server Tool
To overcome the bandwidth limit and avoid that players already on the server get network issues due to other players downloading the shared data, this tool will work around this problem.
The tool `esm tool-shareddata-server` will automatically generate a zip file from the current shared data folder of the running scenario and serve them in a custom webserver especially written for that. With this, you can provide your players an alternative way to download the shared data without being limited by eleon. They'll have to unpack that shared data into their game installation manually though.
Since the webserver will run on the same server as the game, it has a sophisticated configuration to limit the bandwith/connection aswell as the global bandwith used. It also includes several security measures like a rate limiter and an internal whitelist for paths.
If your server connection supports e.g. 100 MB/s, you can limit the webserver to not use more than 50MB/s, to make sure the running gameserver network throughput is not affected and the game doesn't lag out the players due to the downloads. If you so desire, you can also limit the bandwith per connection, to make sure that nobody can occupy the whole bandwith. Although this shouldn't take more than 10 seconds, since shared data can't possibly be bigger than 500 MB (current scenario size limit).

The tool serves the the zip and a landing page generated from the `index.template.html` with the instructions on how to use the shared data zip. You can freely edit the template to your liking, following placeholders will be replaced when the tools is started:
- "$SHAREDDATAZIPFILENAME" - with the name of the zipfile according to the configuration
- "$CACHEFOLDERNAME" - with the name of the cache folder according to the configuration

Following values are taken directly from the dedicated yaml:
- "$SRV_NAME", "$SRV_DESCRIPTION", "$SRV_PASSWORD", "$SRV_MAXPLAYERS", "$MAXALLOWEDSIZECLASS", "$PLAYERLOGINPARALLELCOUNT", "$PLAYERLOGINFULLSERVERQUEUECOUNT"


The name of the folder in the zip file will be generated by ESM and looks like "MyServerDediGameName_123.234.34.56_123456789", consisting of game name, server ip and unique game id (you can look up the latter in the logfiles). This is usually created automatically by your client once you connect to the server - this is what we are replacing. If for some reason the cache folder name is generated wrong and you need it to be different, use `useCustomCacheFolderName: true` and provide a custom folder name in `customCacheFolderName: DediGame_127.0.0.1_123456789` in the configuration of the download tool.

This tool logs in its own logfile.

#### copyright by Vollinger 2023-2024