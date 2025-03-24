# PassCrack - Password Recovery Tool

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

## Installation Guide

### Prerequisites

#### 1. Install Python

**Windows:**
1. Download the latest Python installer (3.8+) from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. **Important:** Check the box "Add Python to PATH" during installation
4. Click "Install Now"
5. Verify installation by opening Command Prompt and typing: `python --version`

**macOS:**
1. Download the latest Python installer from [python.org](https://www.python.org/downloads/)
2. Run the installer and follow the prompts
3. Verify installation by opening Terminal and typing: `python3 --version`

**Linux:**
```bash
sudo apt update
sudo apt install python3 python3-pip
python3 --version
```

#### 2. Install Required Dependencies

After installing Python, open a Command Prompt (Windows) or Terminal (macOS/Linux) and run:

```bash
# Install required Python packages
pip install paramiko pymupdf pillow requests tqdm
```

Note: `tkinter` is typically included with Python installations, but if it's missing, you can install it:
- Windows: Usually included with the Python installer
- macOS: `brew install python-tk`
- Linux: `sudo apt install python3-tk`

#### 3. Essential External Tool - Hashcat

PassCrack requires Hashcat for password cracking functionality:

**Windows:**
1. Download the latest release from [hashcat.net](https://hashcat.net/hashcat/)
2. Extract the ZIP file to a location on your computer
3. Ensure the hashcat.exe file is accessible from the PassCrack directory, or place it in the same directory as passcrack.py

**macOS:**
```bash
brew install hashcat
```

**Linux:**
```bash
sudo apt install hashcat
```

#### 4. Optional External Tools

For enhanced functionality, install these additional tools:

**Extraction Scripts:**
- **office2john.py**: Download from the [John the Ripper GitHub repo](https://github.com/openwall/john/tree/bleeding-jumbo/run) and place in the application directory
- **pdfbrute.py**: This file should be included with the application for enhanced PDF cracking capabilities

**Full John the Ripper Installation:**
- Windows: Download from [Openwall](https://www.openwall.com/john/)
- macOS: `brew install john`
- Linux: `sudo apt install john`

## Running the Application

After installation, you can run the application with:

```bash
python passcrack.py
```

## Hash Cracking Features

### NTLM & NetNTLMv2 Cracking

PassCrack now features enhanced support for NetNTLMv2 hash cracking:

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

PassCrack includes a dictionary manager for organizing and analyzing wordlists:

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
   - Ensure hashcat is installed and accessible in your PATH, or place it in the same directory as passcrack.py
   - On Windows, you may need to install Visual C++ Redistributable packages

2. **Missing Python Dependencies**:
   - Run `pip install -r requirements.txt` if provided, or install dependencies manually

3. **Permission Issues**:
   - On Windows, you may need to run the program as Administrator
   - On Linux/macOS, ensure proper permissions for the application directory

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