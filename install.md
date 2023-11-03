# From Zero to Running Server

## Fresh install from scratch
### Install ESM

- TODO

### Configure ESM

- edit esm-custom-config.yaml
- set all paths
- all settings from base-config can be overwritten in the custom config. Each yaml "section" has to be copied completely.

### Install Empyrion Dedicated Server

If you already have a installed and working dedicated server, you can skip this step.

- call esm game-install

### Configure Empyrion

- copy esm-dedicated.yaml to empyrion install dir
- copy esm-starter-for-eah.cmd to empyrion install dir
- edit esm-dedicated.yaml to your liking
- edit esm-starter-for-eah.cmd, set proper path to esm install dir

### Configure EAH

- start EAH once, so it copies its mods to the empyrion mod folder
- select the esm-dedicated.yaml
- select the esm-starter-for-eah.cmd
- start & stop server once (to create a new savegame)
- configure game as desired
- stop eah

### Prepare ramdisk

- call esm ramdisk-install, this will move the savegame to the gamesmirror folder
- call esm ramdisk-prepare, this will mount the ramdisk, copy the savegame to it and symlink it back to the empyrion saves folder. This will also externalize the templates if configured. You'll need to repeat this step when you rebooted your server.

### Start server

#### via ESM
- call esm server-start

#### via EAH
- start eah
- start server

##### copyright by Vollinger 2023