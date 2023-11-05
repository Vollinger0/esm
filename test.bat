@echo off
setlocal enabledelayedexpansion

REM Id = entity id
REM .\EmpyrionPrime.remoteClient.Console.exe request InGameMessageSinglePlayer "{ `"id`": 1000, `"msg`": `"This is a message!`", `"prio`": 1, `"time`": 10 }"

REM set "cmd={ \"msg\": \"This is a message!\", \"prio\": 1, \"time\": 10 }"
REM Id omitted
REM .\EmpyrionPrime.remoteClient.Console.exe request InGameMessageAllPlayers !cmd!

REM Id = Faction Id
REM .\EmpyrionPrime.remoteClient.Console.exe request InGameMessageFaction "{ `"id`": 100, `"msg`": `"This is a message!`", `"prio`": 1, `"time`": 10 }"

timeout 5
for /L %%i in (1,1,3) do (
    REM .\EmpyrionPrime.remoteClient.Console.exe request InGameMessageAllPlayers "{ \"msg\": \"from test.bat prio: %%i\", \"prio\": %%i, \"time\": 3000 }"
    .\EmpyrionPrime.remoteClient.Console.exe request InGameMessageAllPlayers "{ \"msg\": \"alert from test.bat prio: %%i\", \"prio\": 0, \"time\": 3000 }"
    echo %ERRORLEVEL%
    REM call:talktoserver server asshat %%i
    REM call:talktoglobal global man %%i
    timeout 3
)
goto :eof


:talktoserver
.\EmpyrionPrime.remoteClient.Console.exe run "say 'Hello server %*'"
exit /bat


:talktoglobal
.\EmpyrionPrime.remoteClient.Console.exe run "SAY 'Hey global %*'"
exit /b