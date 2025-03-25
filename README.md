# P4wnForge - Password Recovery Tool

![P4wnForge](P4wnForge.webp)

A comprehensive password recovery application for various file formats including Office documents, PDFs, NTLM and NetNTLMv2 hashes, and more.

Developed by Detective Aaron Cuddeback

## Features

- Microsoft Office document password recovery (Word, Excel, PowerPoint)
- PDF password recovery
- NTLM & NetNTLMv2 hash cracking
- Dictionary management with download capabilities
- SSH file browser with session management
- Dark/Light theme support
- Real-time cracking progress display

## Quick Start - One-Click Launcher

P4wnForge includes a simple one-click launcher that automatically installs all required dependencies and starts the application:

1. Download or clone the repository
2. Run `create_shortcut.bat` to create the program shortcut
3. Double-click on the newly created `Start_P4wnForge` shortcut (you can copy it to your desktop)
4. The program will silently install all required dependencies and launch the application

The shortcut created by this method will work properly even when the P4wnForge folder is moved or copied to a different computer.

## Manual Installation Guide

If you prefer to install P4wnForge manually, follow these steps:

### Prerequisites

#### 1. Install Python

1. Download the latest Python installer (3.8+) from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. **Important:** Check the box "Add Python to PATH" during installation
4. Click "Install Now"
5. Verify installation by opening Command Prompt and typing: `python --version`

#### 2. Install Required Dependencies

After installing Python, open a Command Prompt and run:

```bash
# Install required Python packages
pip install -r requirements.txt
```

Note: `tkinter` is typically included with Python installations, but if it's missing, you can reinstall Python and check the "tcl/tk and IDLE" option.

#### 3. Essential External Tool - Hashcat

P4wnForge requires Hashcat for password cracking functionality:

1. Download the latest release from [hashcat.net](https://hashcat.net/hashcat/)
2. Extract the ZIP file to a location on your computer
3. Ensure the hashcat.exe file is accessible from the P4wnForge directory, or place it in the same directory as p4wnforge.py

#### 4. Optional External Tools

For enhanced functionality, ensure these additional tools are available:

**Extraction Scripts:**
- **office2john.py**: Should be included with the application for Office document hash extraction
- **pdfbrute.py**: Should be included with the application for enhanced PDF cracking capabilities

**Full John the Ripper Installation:**
- Download from [Openwall](https://www.openwall.com/john/) for additional cracking capabilities

## Running the Application

After installation, you can run the application in one of these ways:

1. Double-click the `Start_P4wnForge` shortcut created with `create_shortcut.bat`
2. Run `P4wnForge.bat` directly
3. Or using the Python interpreter:
   ```bash
   python p4wnforge.py
   ```

## Hash Cracking Features

### NTLM & NetNTLMv2 Cracking

P4wnForge features enhanced support for NetNTLMv2 hash cracking:

1. **Automatic Format Detection**: The application can detect and properly format NetNTLMv2 hashes from common capture formats
2. **Default NetNTLMv2 Mode**: The hash type dropdown now defaults to NetNTLMv2 for convenience
3. **Comprehensive Password Detection**: The application will detect cracked passwords via multiple methods:
   - Real-time output monitoring
   - Output file checking
   - Hashcat potfile verification

### Hash File Format Support

- **NTLM Hashes**: Simple 32-character hash strings
- **NetNTLMv2 Hashes**: Complex format like `Username::Domain:Challenge:Hash:Blob`
- **Wireshark/Responder Captures**: Handles common output formats from network capture tools

### Usage:

1. Select your hash file (or paste the hash directly)
2. Choose the hash type (NTLM, NetNTLMv2, etc.)
3. Select attack mode (Dictionary or Bruteforce)
4. Start cracking!

## Dictionary Management

P4wnForge includes a dictionary manager for organizing and analyzing wordlists:

- Download common wordlists directly from the application
- Add custom wordlists
- Analyze password statistics
- Select wordlists for cracking operations

## PDF Password Cracking 

The PDF cracking functionality uses a specialized module for enhanced performance:

1. **Dedicated PDF Bruteforce Module**: Uses the included pdfbrute.py module for efficient PDF cracking
2. **No wordlist requirement for bruteforce mode**: Supports pure bruteforce attacks on PDF files
3. **Enhanced error handling**: Better error detection and reporting during the cracking process
4. **Multi-library support**: Can use different PDF libraries for optimal compatibility

## Troubleshooting

### Common Issues

1. **Hashcat Not Found**:
   - Ensure hashcat is installed and accessible in your PATH, or place it in the same directory as p4wnforge.py
   - You may need to install Visual C++ Redistributable packages

2. **Missing Python Dependencies**:
   - Run `pip install -r requirements.txt` if provided, or install dependencies manually

3. **Permission Issues**:
   - You may need to run the program as Administrator if you encounter permission errors

4. **Shortcut Problems (Missing Icon or Not Working)**:
   - Run `create_shortcut.bat` to generate a new shortcut
   - The batch file will create shortcuts both in the program folder and on your desktop
   - This fixes issues with missing icons or shortcuts that don't work after moving the program
   
   If the automatic fix doesn't work, you can manually create a shortcut:
   - Right-click in the P4wnForge folder and select "New > Shortcut"
   - Enter `P4wnForge.bat` as the target (use the relative path)
   - Name it "Start_P4wnForge"
   - Right-click the new shortcut and select "Properties"
   - Click "Change Icon" and browse to the P4wnForge_icon.ico file in the same folder

## License

MIT License

Copyright (c) 2024 Detective Aaron Cuddeback

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE. 