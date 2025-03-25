#!/usr/bin/env python3
"""
P4wnForge Force Shortcut Fixer
------------------------------
This script forcefully fixes the shortcut issue by:
1. Extracting the icon from the executable if possible
2. Rebuilding the icon from the webp image if available
3. Creating a new shortcut with the correct relative paths
"""

import os
import sys
import platform
import subprocess
import time
import base64
import tempfile
import shutil

def install_dependencies():
    """Install required dependencies"""
    print("Installing required dependencies...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pywin32", "winshell", "pillow"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("Dependencies installed successfully.")
        
        # Give time for DLLs to register properly
        time.sleep(1)
        return True
    except Exception as e:
        print(f"Error installing dependencies: {str(e)}")
        print("\nPlease try to manually install the required packages with:")
        print("pip install pywin32 winshell pillow")
        return False

def ensure_correct_extension(path, default_ext=None):
    """Ensure the path has the correct extension"""
    _, ext = os.path.splitext(path)
    
    # If the path has no extension and a default is provided, add it
    if not ext and default_ext:
        if not default_ext.startswith('.'):
            default_ext = '.' + default_ext
        return path + default_ext
    
    return path

def create_icon_file(script_dir):
    """Create the icon file by any means necessary"""
    icon_path = os.path.join(script_dir, "P4wnForge_icon.ico")
    
    # Check if icon already exists
    if os.path.exists(icon_path):
        print(f"Icon file already exists at {icon_path}")
        return True
    
    print(f"Icon file not found at {icon_path}. Attempting to create it...")
    
    # Try to use existing webp image
    webp_icon = os.path.join(script_dir, "P4wnForge.webp")
    if os.path.exists(webp_icon):
        try:
            # Try to convert webp to ico using PIL
            print("Found webp icon, converting to .ico format...")
            try:
                from PIL import Image
                img = Image.open(webp_icon)
                img.save(icon_path, format="ICO")
                print(f"Successfully created {icon_path} from webp image")
                return True
            except ImportError:
                print("PIL/Pillow not available for image conversion")
            except Exception as e:
                print(f"Error converting image: {e}")
        except Exception as e:
            print(f"Error handling webp icon: {e}")
    
    # If we get here, we couldn't create the icon from existing files
    # As a last resort, create a simple icon
    try:
        print("Creating a basic icon file...")
        try:
            from PIL import Image, ImageDraw
            
            # Create a simple colored square icon
            img = Image.new('RGB', (256, 256), color=(41, 128, 185))
            draw = ImageDraw.Draw(img)
            
            # Add some text
            draw.rectangle([20, 20, 236, 236], outline=(255, 255, 255), width=5)
            img.save(icon_path, format="ICO")
            print(f"Created a basic icon at {icon_path}")
            return True
        except ImportError:
            print("PIL/Pillow not available for image creation")
        except Exception as e:
            print(f"Error creating basic icon: {e}")
    except Exception as e:
        print(f"Error creating icon: {e}")
    
    print("Could not create icon file by any method.")
    return False

def create_portable_shortcut():
    """Create a portable shortcut with relative paths"""
    if platform.system() != "Windows":
        print("This script only works on Windows.")
        return False
    
    # Install dependencies first
    if not install_dependencies():
        return False
    
    try:
        # Need to import after installation
        import winshell
        from win32com.client import Dispatch
        
        # Get the current script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Force create the icon file
        create_icon_file(script_dir)
        
        # Path for the local shortcut in the application directory
        local_shortcut_path = os.path.join(script_dir, "Start_P4wnForge.lnk")
        
        print(f"Creating portable shortcut at: {local_shortcut_path}")
        
        # Create/update the shortcut
        shell = Dispatch('WScript.Shell')
        local_shortcut = shell.CreateShortCut(local_shortcut_path)
        
        # Use relative paths for the portable shortcut
        # Ensure the target path has the correct extension
        batch_file = ensure_correct_extension("P4wnForge", "bat")
        local_shortcut.Targetpath = batch_file
        local_shortcut.WorkingDirectory = "."  # Current directory
        
        # Set icon location
        icon_path = os.path.join(script_dir, "P4wnForge_icon.ico")
        if os.path.exists(icon_path):
            # Use explicit formatting for the icon location - file path and index 0
            icon_rel_path = ensure_correct_extension("P4wnForge_icon", "ico")
            local_shortcut.IconLocation = f"{icon_rel_path},0"  # Use relative path with index
            print(f"Using icon: {icon_rel_path} (relative path)")
        else:
            print(f"Warning: Icon file still not found at {icon_path}")
            # Try to use system icons as fallback
            local_shortcut.IconLocation = "shell32.dll,4"  # Generic program icon from shell32.dll
        
        local_shortcut.Description = "P4wnForge Password Recovery Tool"
        local_shortcut.save()
        
        print(f"Shortcut created successfully: {local_shortcut_path}")
        print("This shortcut will work when the P4wnForge folder is moved or copied.")
        
        # Optionally also create a desktop shortcut
        try:
            desktop = winshell.desktop()
            desktop_shortcut_path = os.path.join(desktop, "Start_P4wnForge.lnk")
            
            print(f"Creating desktop shortcut at: {desktop_shortcut_path}")
            
            desktop_shortcut = shell.CreateShortCut(desktop_shortcut_path)
            desktop_shortcut.Targetpath = os.path.join(script_dir, ensure_correct_extension("P4wnForge", "bat"))
            desktop_shortcut.WorkingDirectory = script_dir
            
            if os.path.exists(icon_path):
                desktop_shortcut.IconLocation = f"{icon_path},0"
            else:
                # Try to use system icons as fallback
                desktop_shortcut.IconLocation = "shell32.dll,4"  # Generic program icon from shell32.dll
                
            desktop_shortcut.Description = "P4wnForge Password Recovery Tool"
            desktop_shortcut.save()
            
            print(f"Desktop shortcut also created: {desktop_shortcut_path}")
        except Exception as e:
            print(f"Note: Desktop shortcut could not be created: {str(e)}")
            print("This might be due to permission issues. You can manually copy the shortcut to your desktop.")
        
        return True
    except Exception as e:
        print(f"Error creating shortcut: {str(e)}")
        
        # Special handling for common errors
        error_str = str(e).lower()
        if "no module named" in error_str:
            print("\nIt seems the required modules didn't install correctly.")
            print("Please try to manually install the required packages with:")
            print("pip install pywin32 winshell pillow")
        elif "com_error" in error_str:
            print("\nThere was an error with the Windows COM interface.")
            print("Try running this script as Administrator.")
        
        return False

if __name__ == "__main__":
    print("P4wnForge Force Shortcut Fixer")
    print("------------------------------")
    print("This script will forcefully fix shortcut and icon issues.")
    success = create_portable_shortcut()
    
    if success:
        print("\nSuccess! The shortcut has been fixed.")
    else:
        print("\nFailed to fix the shortcut. Please see the error messages above.")
    
    # Keep console open if script was double-clicked
    if len(sys.argv) <= 1:
        input("\nPress Enter to exit...") 