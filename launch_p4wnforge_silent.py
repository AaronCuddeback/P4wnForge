#!/usr/bin/env python3
"""
P4wnForge Silent Launcher
-------------------------
This script silently installs dependencies and launches the P4wnForge application.
"""

import os
import sys
import subprocess
import platform
from subprocess import DEVNULL

def install_dependencies():
    """Install required Python dependencies silently"""
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check if requirements.txt exists
    req_file = os.path.join(script_dir, "requirements.txt")
    if not os.path.exists(req_file):
        with open(req_file, "w") as f:
            f.write("\n".join([
                "paramiko",
                "pymupdf",
                "pillow",
                "requests",
                "tqdm",
                "pikepdf",
                "PyPDF2",
                "pypdf"
            ]))
    
    # Install dependencies using pip
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", req_file],
            stdout=DEVNULL,
            stderr=DEVNULL
        )
        return True
    except subprocess.CalledProcessError:
        return False

def check_hashcat():
    """Check if hashcat is available"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check if hashcat executable exists in the current directory
    if platform.system() == "Windows":
        hashcat_path = os.path.join(script_dir, "hashcat.exe")
    else:
        hashcat_path = os.path.join(script_dir, "hashcat.bin")
    
    if os.path.exists(hashcat_path):
        return True
    
    try:
        # Try to run hashcat to see if it's in PATH
        subprocess.check_call(
            ["hashcat", "--version"],
            stdout=DEVNULL,
            stderr=DEVNULL
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def launch_application():
    """Launch the P4wnForge application"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_script = os.path.join(script_dir, "p4wnforge.py")
    
    if not os.path.exists(app_script):
        return False
    
    try:
        subprocess.Popen(
            [sys.executable, app_script],
            stdout=DEVNULL,
            stderr=DEVNULL
        )
        return True
    except Exception:
        return False

def create_shortcut_silently():
    """Create a desktop shortcut without asking (Windows only)"""
    if platform.system() != "Windows":
        return
    
    try:
        # First, install required packages
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pywin32", "winshell"],
            stdout=DEVNULL,
            stderr=DEVNULL
        )
        
        # Give time for DLLs to register properly
        import time
        time.sleep(1)
        
        import winshell
        from win32com.client import Dispatch
        
        # Get absolute paths for shortcut creation
        script_dir = os.path.dirname(os.path.abspath(__file__))
        batch_file = os.path.join(script_dir, "P4wnForge.bat")
        icon_path = os.path.join(script_dir, "P4wnForge_icon.ico")
        
        desktop = winshell.desktop()
        shortcut_path = os.path.join(desktop, "Start_P4wnForge.lnk")
        
        # Only create if it doesn't exist or if we're forcing recreation
        if not os.path.exists(shortcut_path) or len(sys.argv) > 1 and sys.argv[1] == "--force-shortcut":
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = batch_file
            shortcut.WorkingDirectory = script_dir
            if os.path.exists(icon_path):
                shortcut.IconLocation = f"{icon_path},0"  # Add index for proper icon reference
            shortcut.Description = "P4wnForge Password Recovery Tool"
            shortcut.save()
            
            # Always create/update shortcut in the application directory with relative paths
            # This will be the one users can copy to another machine
            local_shortcut_path = os.path.join(script_dir, "Start_P4wnForge.lnk")
            local_shortcut = shell.CreateShortCut(local_shortcut_path)
            
            # Use relative paths for the portable shortcut
            # The shortcut will use the P4wnForge.bat file in the same directory as the .lnk file
            local_shortcut.Targetpath = "P4wnForge.bat"
            local_shortcut.WorkingDirectory = "."  # Current directory
            if os.path.exists(icon_path):
                local_shortcut.IconLocation = "P4wnForge_icon.ico,0"  # Use relative path with index
            local_shortcut.Description = "P4wnForge Password Recovery Tool"
            local_shortcut.save()
            
            # If this was called from the --fix-shortcut argument, print a success message
            if len(sys.argv) > 1 and sys.argv[1] == "--fix-shortcut":
                print(f"Shortcut fixed successfully:")
                print(f"1. Portable shortcut created at: {local_shortcut_path}")
                print(f"2. Desktop shortcut created at: {shortcut_path}")
                print("\nThe portable shortcut uses relative paths and can be moved with the P4wnForge folder.")
            
            return True
    except Exception as e:
        # If this was called with --fix-shortcut, show the error
        if len(sys.argv) > 1 and sys.argv[1] == "--fix-shortcut":
            print(f"Error creating shortcut: {str(e)}")
            print("\nPlease try the separate fix_shortcut.py script instead.")
        return False

if __name__ == "__main__":
    # Check if we're just being asked to fix/recreate the shortcut
    if len(sys.argv) > 1 and sys.argv[1] == "--fix-shortcut":
        create_shortcut_silently()
        sys.exit(0)
        
    # Install dependencies
    install_dependencies()
    
    # Check for hashcat
    check_hashcat()
    
    # Launch the application
    launch_application()
    
    # Create shortcut without asking on first run (check for config file)
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "p4wnforge_config.json")
    if not os.path.exists(config_path):
        create_shortcut_silently() 