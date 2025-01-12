@echo off
setlocal enabledelayedexpansion
:: just a wrapper script to be called by EAH that will start esm asynchroneously (not blocking the caller)
::
:: by vollinger 20231102

:: ################################################################################################################
:: ## CONFIGURATION

:: path to esm tool installation
:: ************** UNCOMMENT THE FOLLOWING LINE AND MAKE SURE THE PATH POINTS TO THE ESM INSTALLATION **************
:: set "esmPath=D:\Servers\Tools\esm"

:: esm command to execute asynchroneously in the background
set "esmCommand=esm -v version"

:: ################################################################################################################
:: ## script start

:: own logfile
set "logFile=%~dp0%~n0.log"

IF NOT EXIST !esmPath! (
	call:techo "ERROR: Script was not set up properly. Please edit %~n0 and set the path to esm properly." 
	exit /b 1
)

call:techo "Calling esm script: !esmCommand!"

cd %esmPath%
start cmd /c !esmCommand!
set scriptReturnCode=%ERRORLEVEL%

:: handle the return code of the start command (not the esm command)
IF "!scriptReturnCode!"=="0" (
	call:techo "ESM call ended successfully."
) ELSE (
	call:techo "ESM call failed for an unknown reason returncode: '!scriptReturnCode!'"
)

call:timeout 5

goto :eof

:techo
	for /f "tokens=*" %%a in ('powershell -Command "(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"') do set "datetime=%%a"
	echo [%datetime%] %*	
	echo [%datetime%] %* >>%logFile%
	exit /b

:timeout
	timeout /T %1 /NOBREAK >NUL
	exit /b
