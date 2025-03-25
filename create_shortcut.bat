@echo off
title P4wnForge Shortcut Creator
echo.
echo P4wnForge Shortcut Creator
echo ========================
echo.
echo This will create shortcuts for the P4wnForge Password Recovery Tool.
echo.
echo - A shortcut will be created in the current folder (portable)
echo - A shortcut will also be created on your desktop
echo - Both shortcuts will have the correct icon
echo.
echo Running...
echo.

REM Run the Python script
python "%~dp0force_fix_shortcut.py"

echo.
echo Process completed.
echo Press any key to exit...
pause > nul 