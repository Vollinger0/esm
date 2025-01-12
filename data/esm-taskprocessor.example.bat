@echo off
setlocal enabledelayedexpansion
:: A simple bash script that will execute tasks in a todo file and move them to the done file
:: 
:: To be executed via a scheduling app (like EAH or EWA's timetable) on restarts or similar.
::
:: Perfect for queueing up maintenance tasks in a file, then have them be done automatically on a restart -
:: especially if the tasks require the server to be shut down, e.g. updating the game, the scenario, wiping territories, etc.
::
:: by vollinger 20250112

:: ################################################################################################################
:: ## CONFIGURATION

:: path to esm tool installation
:: ************** UNCOMMENT THE FOLLOWING LINE AND MAKE SURE THE PATH POINTS TO THE ESM INSTALLATION **************
::set "esmPath=D:\Servers\Tools\esm"
:: ************** UNCOMMENT THE FOLLOWING LINE AND MAKE SURE THE PATH POINTS TO THE TASK FOLDER **************
::set "esmTaskDir=D:\Servers\Tools\esm\tasks"

:: ################################################################################################################
:: ## script start

:: own logfile
set "logFile=%~dp0%~n0.log"

IF NOT EXIST !esmPath! (
	call:techo "ERROR: Script was not set up properly. Please edit %~n0 and set the path to esm properly." 
	exit /b 1
)

IF NOT EXIST !esmTaskDir! (
	call:techo "ERROR: Script was not set up properly. Please edit %~n0 and set the path to the tasks directory at !esmTaskDir! properly. If the directory does not exist, create it!" 
	exit /b 1
)

:: Define file names
set "TODO_FILE=!esmTaskDir!\TODO.txt"
set "WIP_FILE=!esmTaskDir!\IN_PROGRESS.txt"
set "DONE_FILE=!esmTaskDir!\DONE.txt"
set "FAILED_FILE=!esmTaskDir!\FAILED.txt"
set "TEMP_FILE=!esmTaskDir!\temp.txt"

:: Create status files if they don't exist
if not exist "!TODO_FILE!" type nul > "!TODO_FILE!"
if not exist "!WIP_FILE!" type nul > "!WIP_FILE!"
if not exist "!DONE_FILE!" type nul > "!DONE_FILE!"
if not exist "!FAILED_FILE!" type nul > "!FAILED_FILE!"
if not exist "!TEMP_FILE!" type nul > "!TEMP_FILE!"

:processNextTask
    :: Check if the TODO file is empty
    for /f %%i in ('type "!TODO_FILE!" ^| find /c /v ""') do set linecount=%%i
    if %linecount% equ 0 (
		call:techo "No tasks in !TODO_FILE! to execute, edit the file and add a command per line"
		goto :finished
	)

	::@echo on
    :: Get the first line from the TODO file
	for /f "tokens=* delims=" %%a in ('type "!TODO_FILE!"') do (
		set "task=%%a"
		goto :processTask
	)	

:processTask
    :: Move the task to WIP (overwrite if anything is there from a previous interruption)
    echo !task! > "!WIP_FILE!"

    :: Remove the first line from TODO (using a temporary file)
    (for /f "skip=1 tokens=* delims=" %%d in ('type "!TODO_FILE!"') do (
        echo %%d
    )) > "!TEMP_FILE!"
    move /y "!TEMP_FILE!" "!TODO_FILE!" >nul
	
	call:techo "Executing task: !task!"
	cd !esmPath!
	!task! 2>&1 >>!logFile!
	set scriptReturnCode=%ERRORLEVEL%

	:: handle the return code
	IF "!scriptReturnCode!"=="0" (
		echo [%datetime%] DONE: "!task!" >> !DONE_FILE!
		call:techo "Task finished successfully."
	) ELSE (
		echo [%datetime%] FAILED: "!task!" >> !FAILED_FILE!
		call:techo "Task failed for an unknown reason returncode: '!scriptReturnCode!'. Check the logfile"
	)

    :: Clear the WIP file
    echo. > "!WIP_FILE!"
	call:timeout 3
	call :processNextTask
	exit /b

:finished
	call:techo "Finished processing tasks."
	goto :eof

:techo
	for /f "tokens=*" %%a in ('powershell -Command "(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"') do set "datetime=%%a"
	echo [%datetime%] %*	
	echo [%datetime%] %* >>%logFile%
	exit /b

:timeout
	timeout /T %1 /NOBREAK >NUL
	exit /b
