# About scenarios and shared data downloads

The games network bandwith seems to be limited to ~10MB/s for the whole server. This bandwith has to be shared by all players currently playing and all players who want to download anything. If you have big scenario updates, prepare to have network issues for the rest of the day. Unless, of course, you use the shared data server tool (read about the [shared data tool](readme_shareddata.md)).

## Things to consider
The game does not check for content changes on the SharedData-files of the scenario. It only checks for the last modification date of these files. Once that changes, a re-download is triggered for the client. If you touch all the files in the shared folder, the clients will redownload the whole scenario although nothing really changed.
The `esm scenario-update` command will make sure this does not happen and will update the game scenario files only, if their content really changed, minimizing the need for everyone to redownload things.

## The Shared Data Server Tool
To overcome the bandwidth limit and avoid that players already on the server get network issues due to other players downloading the shared data, this tool will work around this problem.
The tool `esm tool-shareddata-server` will automatically generate a zip file from the current shared data folder of the running scenario and serve them in a custom http webserver especially written for that. With this, you can provide your players an alternative way to download the shared data without being limited by empyrion's limitations. They'll have to unpack that shared data into their game installation manually though, unless you also enable the SharedDataURL feature mentioned below.

Since Empyrion v1.11.7, the game server now also supports a rather dangerous feature, where an admin can configure the SharedDataURL to externalize the client download for the shared data, but you have to create the zipfile with the correct structure yourself and add the correct configuration. If there are game or scenario updates, you have to repeat that and make sure the url in the configuration changes.
Be aware though, it has some drawbacks:
### IF THE CONTENT OF THE ZIPFILE AND THE SERVER SCENARIO DATA ARE NOT IDENTICAL IT WILL BREAK THE GAME ON THE CLIENTS
### If the URL did NOT change even though the file did, the game clients will NOT download the file AT ALL AND BREAK THE GAME FOR THE CLIENTS
### IF the url is not reachable for some reason, the game clients will NOT download the file AND BREAK THE GAME FOR THE CLIENTS
### If the zip file does not have the required structure it will get ignored and break the game on the clients.
### You have to recreate that file on EVERY game or scenario change, no matter if its only a change in a little file or not

ESM will completely automate this for you to minimize those errors. You only have to set enable the flag `useSharedDataURLFeature` in the esm configuration.
The shared-data-tool will serve another zip file of the shared data with a changing filename, since its url needs to be changed every time the file is recreated. It will look like this `SharedData_20240621_235959.zip`. The configuration for the SharedDataURL will be **automatically** changed while the tool is running (the dedicated yaml is edited), and changed back when the tool is stopped. The change will look like this:
```
  SharedDataURL: _http://123.456.789.123:12345/SharedData_20240621_235959.zip
```
### If you use this feature, make sure to have the shared-data-tool server started when serving the game and make sure to restart the game server whenever you started or stopped the data-tool.**
ESM will check this for you on server start and will **ABORT** the server start if there is a shared data url configured that is **not** reachable to avoid having an invalid configuration.

You can disable the automatic configuration in the dedicated yaml by setting `autoEditDedicatedYaml` to false in the config.
You can override the automatic hostip and port generation by setting your own `customExternalHostNameAndPort`, which should look something like: 'https://my-server.com:12345'
You can override the generation of the whole url and have esm set your own custom url by setting `customSharedDataURL`, which should look something like: 'https://my-server.com:54321/SharedData.zip'

Since the webserver will run on the same server as the game and probably be publicly available, it has a sophisticated configuration to limit the bandwith/connection aswell as the global bandwith used. It also includes several security measures like a rate limiter and an internal whitelist for paths.
If your server connection supports e.g. 100 MB/s, you can limit the webserver to not use more than e.g. 50MB/s, to make sure the running gameserver network throughput is not affected and the game doesn't lag out the players due to the downloads. If you so desire, you can also limit the bandwith per connection, to make sure that nobody can occupy the whole bandwith. Although this shouldn't take more than 10 seconds, since shared data can't possibly be bigger than 500 MB (current scenario size limit). You can also rate-limit the amount of requests per minute per IP, to avoid simple DoS-attacks (default: 10/m). Check the `esm-default-config.example.yaml` for all configuration options, especially configure the port that is publicly available for your server, since the game clients of your players will need to connect to that.

The tool serves both zips and a landing page generated from the `index.template.html` with the instructions on how to use the manual shared data zip. You can freely edit the template to your liking, following placeholders will be replaced when the tools is started:
- "$SHAREDDATAZIPFILENAME" - with the name of the manual zipfile according to the configuration
- "$CACHEFOLDERNAME" - with the name of the cache folder according to the configuration

Following values are taken directly from the dedicated yaml:
- "$SRV_NAME", "$SRV_DESCRIPTION", "$SRV_PASSWORD", "$SRV_MAXPLAYERS", "$MAXALLOWEDSIZECLASS", "$PLAYERLOGINPARALLELCOUNT", "$PLAYERLOGINFULLSERVERQUEUECOUNT", "$SRV_PORT"
Following values will be provided by esm:
- "$SRV_IP" - with the external server ip (may not be accurate if your server is behind a proxy or similar)

The name of the folder in the zip file will be generated by ESM and looks like "MyServerDediGameName_123.234.34.56_123456789", consisting of game name, server ip and unique game id (you can look up the latter in the logfiles). This is usually created automatically by your client once you connect to the server - this is what we are replacing. If for some reason the cache folder name is generated wrong and you need it to be different, use `useCustomCacheFolderName: true` and provide a custom folder name in `customCacheFolderName: DediGame_127.0.0.1_123456789` in the configuration of the download tool.

This tool logs in its own logfile.

### Recommendation
I would recommend to use the shareddata-server at the beginning of a season, or on *big* scenario changes **only**. Turn it off when there are only minor changes. This will ensure that minor changes do NOT trigger a redownload of the whole file for all players, and still offers new players a quick enough way to get onto the server. For small changes, the old way (file-by-file sync trough the gameserver) is still good enough and faster.
Remember that when you turn it on, all your players will have to redownload the newly created file.

#### copyright by Vollinger 2023-2024
