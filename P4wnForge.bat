@echo off
title P4wnForge
echo P4wnForge Password Recovery Tool
echo Starting application...

REM Create a VBScript file to run the application without showing a console window
echo Set objShell = CreateObject("WScript.Shell") > "%temp%\p4wnforge_invisible.vbs"
echo objShell.Run "cmd /c python ""%~dp0launch_p4wnforge_silent.py""", 0, False >> "%temp%\p4wnforge_invisible.vbs"

REM Run the VBScript
start "" /b wscript.exe "%temp%\p4wnforge_invisible.vbs"

REM Exit this batch file after 1 second to allow the VBScript to start
ping -n 2 127.0.0.1 > nul
exit 