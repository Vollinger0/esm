# ESM - Empyrion Server Manager

Sophisticated console client to manage an Empyrion Galactic Survival Dedicated Server.
Built to manage servers with a *lot* of players and *huge* savegames (>>10GB) perfomantly, adding a lot of performance optimizations to the way the server runs.
The main features being fully automated support for running the game on a ramdisk, a blazing fast rolling backup system and a series of tools for managing the galaxy.

## Features

- automatically sets up and runs a game on a ramdisk, which eliminates most server performance problems
- provides its own (eah compatible) rolling mirror backup system, that backs up a 50GB savegame in under a minute without even affecting game server performance
- ability to create static (zipped) backups
- ability to "prepare" the filesystem for ramdisk usage, aswell as to rever that again.
- deleteall function to remove any traces of an existing savegame, when you want to start a new season
- wipe tool for wiping playfields with no player or player-owned terrain placeables or structures.
- tool to clear the "discovered-by" infos from playfields and/or systems
- purge-tools to delete old playfield files, delete the related structures and templates - this will keep your savegame small if used regularly.
- some other tools to clean up and remove obsolete files and data
- can install the game for you (from steam)
- can update the game for you (from steam)
- fully integrated to be used with EAH
- various tools to manage the galaxy
- almost all features, limits, timeouts and paths are configurable
- extensive logfile with a ton of information

## All about performance and the ramdisk

Definitely a [must read](performance.md).

## All about the backups

You'll want to [read this](backups.md).

## install ESM, the game, everything

Please follow this [path](install.md).

## developing and contributing

Please follow this [rabbit hole](development.md).

#### copyright by Vollinger 2023
