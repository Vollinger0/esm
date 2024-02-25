# From Zero to Hero

This guides you step-by-step through the whole installation process, if you didn't have a server to begin with.
If you already have a running empyrion game server and even an existing savegame, its even easier since you can skip a few steps.

## Installing ESM and Empyrion

### Install ESM

1. just unpack the zip to a folder of your choice, e.g. `D:\Servers\Tools\esm`
2. create a copy of [esm-custom-config.example.yaml](esm-custom-config.example.yaml) as `esm-custom-config.yaml`
2. open a windows console/terminal, cd into that directory and call `esm -v check-requirements`
3. if you see colored output with timestamps, you succeeded.

### Configure ESM

- edit the `esm-custom-config.yaml`, read the esm-*.example files for details on the attributes
- set all paths properly, especially the path to the empyrion installation directory and dedicated yaml
- look at the settings in the example files, all of these can be overwritten in your custom config. Yaml arrays have to be copied completely.
- add the galaxy-territory-definitions - these are dependent on the scenario and version and are needed for the tool the *tool-wipe-empty-playfields*
- call `esm check-requirements` to check if everything is fine after editing the config file and/or installing the requirements.

### Install Empyrion Dedicated Server

If you already have a installed and working dedicated server, you can skip this step.

- call `esm game-install`. This will download and install the game using steamcmd, this might take a bit.
- go to your installation `_CommonRedist\vcredist\2019\` and install the c++ redistributable for your OS, probably `Microsoft Visual C++ 2019 x64.cmd`

### Configure Empyrion

- copy [esm-dedicated.example.yaml](esm-dedicated.example.yaml) as `esm-dedicated.yaml` to the empyrion install dir, or configure the name of the one you are using.
- copy [esm-starter-for-eah.example.cmd](esm-starter-for-eah.example.cmd) as `esm-starter-for-eah.cmd` to the empyrion install dir
- edit the copied `esm-dedicated.yaml` in the empyrion install dir to your liking (alternatively, with EAH)
- edit the copied `esm-starter-for-eah.cmd` in the empyrion install dir, set the proper path to **esm install dir**.

### Configure EAH

- start EAH once, so it copies its mods to the empyrion mod folder
- select the `esm-dedicated.yaml` you created previously
- select the `esm-starter-for-eah.cmd` you created and edited previously
- configure tool, server and game in EAH as desired
- start & stop server from EAH once (to create a new savegame and copy the epm and epf mods to the game's mod folder)
- stop eah

### Prepare ramdisk

If you are NOT using a ramdisk (and disabled it in the config), skip this section.

- call `esm ramdisk-install`, this will move the savegame to the gamesmirror folder
- call `esm ramdisk-setup`, this will mount the ramdisk, copy the savegame to it and symlink it back to the empyrion saves folder. This will also externalize the templates if configured. You'll need to repeat this step when you rebooted your server.

### Start server

#### via ESM
- call `esm server-start`

#### via EAH
- start eah
- start server

**PROFIT**

## Install/Update Scenario

Esm provides a special tool that ensures that scenario updates stay minimal to avoid players having to download files that didn't change.

- download the scenario from the workshop, copy it to a separate folder on the server, e.g. `D:\Servers\Scenarios\ReforgedEden`
- configure exactly that path in your custom config at `updates -> scenariosource`
- run `esm scenario-update` - this will synchronize the scenario files into the game's scenario folder *with the same name*
- configure the Scenario name in your dedicated.yaml or via EAH.

The tool will update any file with changed **content** by comparing them via hashes, it will ignore other attributes or time attributes. All of these 
trigger the slow re-downloads for nothing, since the game is not overly smart in finding out what changed.

#### copyright by Vollinger 2023-2024