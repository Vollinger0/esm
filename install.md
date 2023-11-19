# From Zero to Hero

This guides you step-by-step through the whole installation process, if you didn't have a server to begin with.
If you already have a running empyrion game server and even an existing savegame, its even easier since you can skip a few steps.

## Installing ESM and Empyrion

### Install ESM

1. just unpack the zip to a folder of your choice, e.g. `D:\Servers\Tools\esm`
2. open a windows console/terminal, cd into that directory and call `esm -v check-requirements`
3. if you see colored output with timestamps, you succeeded.

### Configure ESM

- edit [esm-custom-config.yaml](esm-custom-config.yaml) (do **not** edit the esm-base-config.yaml, you can use to read about all the config options though)
- set all paths properly, especially the path to the empyrion installation directory
- look at the settings in esm-base-config.yaml, all of these can be overwritten in the custom config, but each yaml "section" has to be copied completely.
- call `esm check-requirements` to check if everything is fine.

### Install Empyrion Dedicated Server

If you already have a installed and working dedicated server, you can skip this step.

- call `esm game-install`. This will download and install the game using steamcmd, this might take a bit.
- go to your installation `_CommonRedist\vcredist\2019\` and install the c++ redistributable for your OS, probably `Microsoft Visual C++ 2019 x64.cmd`

### Configure Empyrion

- copy [esm-dedicated.yaml](esm-dedicated.yaml) to the empyrion install dir
- copy [esm-starter-for-eah.cmd](esm-starter-for-eah.cmd) to the empyrion install dir
- edit the copied esm-dedicated.yaml in the empyrion install dir to your liking
- edit the copied esm-starter-for-eah.cmd in the empyrion install dir, set proper path to esm install dir

### Configure EAH

- start EAH once, so it copies its mods to the empyrion mod folder
- select the esm-dedicated.yaml you created previously
- select the esm-starter-for-eah.cmd you created and edited previously
- configure tool, server and game in EAH as desired
- start & stop server from EAH once (to create a new savegame and copy the epm and epf mods to the game's mod folder)
- stop eah

### Prepare ramdisk

If you are NOT using a ramdisk (and disabled it in the config), skip this section.

- call `esm ramdisk-install`, this will move the savegame to the gamesmirror folder
- call `esm ramdisk-prepare`, this will mount the ramdisk, copy the savegame to it and symlink it back to the empyrion saves folder. This will also externalize the templates if configured. You'll need to repeat this step when you rebooted your server.

### Start server

#### via ESM
- call `esm server-start`

#### via EAH
- start eah
- start server

**PROFIT**

##### copyright by Vollinger 2023