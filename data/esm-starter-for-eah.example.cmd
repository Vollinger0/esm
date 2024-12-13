@echo off
setlocal enabledelayedexpansion
REM just a wrapper script to be called by EAH that will start esm asynchroneously
REM
REM by vollinger 20231102

REM ################################################################################################################
REM ## CONFIGURATION

REM path to esm tool installation
REM ************** UNCOMMENT THE FOLLOWING LINE AND MAKE SURE THE PATH POINTS TO THE ESM INSTALLATION **************
REM set "esmPath=D:\Servers\Tools\esm"

REM ################################################################################################################
REM ## script start

REM own logfile
set logFile=%~n0.log

IF NOT EXIST !esmPath! (
	call:techo "ERROR: Script was not set up properly. Please edit %~n0 and set the path to esm properly." 
	exit /b 1
)

cd %esmPath%
call:techo "Calling esm script: esm -w -v server-start"

start cmd /c esm -w -v server-start
set scriptReturnCode=%ERRORLEVEL%
IF "!scriptReturnCode!"=="0" (
	call:techo "ESM call ended successfully."
) ELSE (
	call:techo "ESM call failed for an unknown reason returncode: '!scriptReturnCode!'"
)

call:techo "ESM started in the background"
call:timeout 10

goto :eof

:techo
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "datetime=%dt:~0,4%-%dt:~4,2%-%dt:~6,2% %dt:~8,2%:%dt:~10,2%:%dt:~12,2%"
echo [%datetime%] %*
echo [%datetime%] %* >>%logFile%
exit /b

:timeout
timeout /T %1 /NOBREAK >NUL
exit /b
