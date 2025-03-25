#!/usr/bin/env python3
"""
Robust PDF Password Hash Extractor

This script attempts multiple methods to extract password hashes from PDFs
for use with password cracking tools like hashcat and John the Ripper.

Usage:
    python robust_pdf_extract.py <pdf_file>
"""

import sys
import os
import re
import binascii
import struct
import subprocess
import tempfile
import base64

def run_command(cmd):
    """Run a command and return output"""
    try:
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        stdout, stderr = process.communicate()
        return stdout, stderr, process.returncode
    except Exception as e:
        return None, str(e), -1

def has_command(cmd):
    """Check if a command is available"""
    if os.name == 'nt':  # Windows
        cmd = cmd + '.exe'
    try:
        devnull = open(os.devnull, 'w')
        subprocess.Popen([cmd], stdout=devnull, stderr=devnull).communicate()
        return True
    except OSError:
        return False

def extract_with_pdfid(filename):
    """Try to extract information using pdfid if available"""
    if not has_command('pdfid'):
        return None
    
    stdout, stderr, rc = run_command(['pdfid', filename])
    if rc != 0:
        return None
    
    if '/Encrypt' not in stdout:
        return None
    
    # Parse pdfid output
    encrypt_line = None
    for line in stdout.splitlines():
        if '/Encrypt' in line:
            encrypt_line = line
            break
    
    if not encrypt_line:
        return None
    
    return "PDF appears to be encrypted according to pdfid"

def hex_to_binary(hex_string):
    """Convert hex string to binary data"""
    if isinstance(hex_string, bytes):
        hex_string = hex_string.decode('latin1')
    try:
        return binascii.unhexlify(hex_string)
    except:
        return hex_string.encode('latin1')

def scan_for_password_patterns(filename):
    """Scan file for patterns that look like password hashes"""
    try:
        with open(filename, 'rb') as f:
            data = f.read()
        
        # Look for O and U values across the file
        o_patterns = re.findall(rb'/O\s*[<(]([^>)]+)[>)]', data)
        u_patterns = re.findall(rb'/U\s*[<(]([^>)]+)[>)]', data)
        
        if not (o_patterns and u_patterns):
            return None
        
        o_value = o_patterns[0]
        u_value = u_patterns[0]
        
        # Look for revision
        r_patterns = re.findall(rb'/R\s+(\d+)', data)
        r_value = int(r_patterns[0]) if r_patterns else 4  # Default to 4
        
        # Look for permissions
        p_patterns = re.findall(rb'/P\s+(-?\d+)', data)
        p_value = int(p_patterns[0]) if p_patterns else -1
        
        # Look for ID
        id_patterns = re.findall(rb'/ID\s*\[\s*<([^>]+)>', data)
        id_value = id_patterns[0] if id_patterns else None
        
        # Convert values to hex
        try:
            o_hex = binascii.hexlify(hex_to_binary(o_value)).decode()
            u_hex = binascii.hexlify(hex_to_binary(u_value)).decode()
            id_hex = binascii.hexlify(hex_to_binary(id_value)).decode() if id_value else ""
        except:
            # If conversion fails, try a different approach
            o_hex = binascii.hexlify(o_value).decode()
            u_hex = binascii.hexlify(u_value).decode()
            id_hex = binascii.hexlify(id_value).decode() if id_value else ""
        
        # Generate multiple hash formats for different tools
        results = []
        
        # Format for hashcat mode 10400/10500
        if r_value <= 3:
            hashcat_mode = 10400
            if id_hex:
                hash_str = f"$pdf$1*{r_value}*{p_value}*{id_hex}*{u_hex}*{o_hex}"
            else:
                hash_str = f"$pdf$1*{r_value}*{p_value}*{u_hex}*{o_hex}"
        else:  # r_value >= 4
            hashcat_mode = 10500
            if id_hex:
                hash_str = f"$pdf$2*{r_value}*{p_value}*{id_hex}*{u_hex}*{o_hex}"
            else:
                hash_str = f"$pdf$2*{r_value}*{p_value}*{u_hex}*{o_hex}"
        
        results.append(("hashcat", hash_str, hashcat_mode))
        
        # Format for John the Ripper
        john_hash = f"$pdf${r_value}*{p_value}*{id_hex}*{o_hex}*{u_hex}"
        results.append(("john", john_hash, None))
        
        return results
    
    except Exception as e:
        sys.stderr.write(f"Error in pattern scanning: {e}\n")
        return None

def create_test_pdf_hashes():
    """Create some test hashes for reference"""
    test_hashes = [
        # For hashcat mode 10400 (PDF 1.1-1.3)
        "$pdf$1*2*40*-1*0*16*51a4e481d5fb9085d6eda5e4ae7f504b*32*c1ebb7dcb2970ed5aa11036e4cbd7a73*32*c4ff7b9d951437bbd58c4438b1b9f1b38b30c44f",
        
        # For hashcat mode 10500 (PDF 1.4-1.6)
        "$pdf$2*3*40*-1*0*16*7a2c0162d14e838b6d856f2449fba2ff*32*7d2b80b4a90a8c30a221cf6a81c45faf*32*8e35933314080db5542ad46dcf34f59b3f8999b35c669a4e54390e9f0fb0",
        
        # Simplified format seen in some examples
        "$pdf$2*3*-1*51000000000000000000000000000000*52000000000000000000000000000000",
        
        # Another common format
        "$pdf$4*4*128*-1028*1*16*da42ee15d4b3e08fe5b9ecea0f3afd6d*32*c9cc0e9e325464302eb8d2ef4ce181d0*32*c4ff3e868dc3d853020010389652e3e95273b9e4"
    ]
    return test_hashes

def generic_pdf_hash(filename):
    """Generate a generic PDF hash by scanning the file"""
    try:
        with open(filename, 'rb') as f:
            data = f.read()
        
        # Simple check if it's a PDF
        if not data.startswith(b'%PDF-'):
            return None
        
        # Find all hex strings that could be hashes
        hex_strings = re.findall(rb'<([0-9a-fA-F]{32,})>', data)
        if len(hex_strings) < 2:
            return None
        
        # Find things that look like /R values
        r_matches = re.findall(rb'/R\s+(\d+)', data)
        r_value = int(r_matches[0]) if r_matches else 4
        
        # Find things that look like /P values
        p_matches = re.findall(rb'/P\s+(-?\d+)', data)
        p_value = int(p_matches[0]) if p_matches else -1
        
        # Use the first two hex strings as U and O
        u_hex = binascii.hexlify(hex_to_binary(hex_strings[0])).decode()
        o_hex = binascii.hexlify(hex_to_binary(hex_strings[1])).decode()
        
        # Format for different tools
        if r_value <= 3:
            hashcat_mode = 10400
            hash_str = f"$pdf$1*{r_value}*{p_value}*{u_hex}*{o_hex}"
        else:
            hashcat_mode = 10500
            hash_str = f"$pdf$2*{r_value}*{p_value}*{u_hex}*{o_hex}"
        
        return [("hashcat", hash_str, hashcat_mode)]
    
    except Exception as e:
        sys.stderr.write(f"Error in generic hash generation: {e}\n")
        return None

def format_as_john_traditional(filename):
    """Format hash in traditional John format"""
    try:
        with open(filename, 'rb') as f:
            data = f.read()
        
        # Find potential O and U values
        o_match = re.search(rb'/O\s*[<(]([^>)]+)[>)]', data)
        u_match = re.search(rb'/U\s*[<(]([^>)]+)[>)]', data)
        
        if not (o_match and u_match):
            return None
        
        try:
            o_value = hex_to_binary(o_match.group(1))
            u_value = hex_to_binary(u_match.group(1))
        except:
            o_value = o_match.group(1)
            u_value = u_match.group(1)
        
        # Convert to hex
        o_hex = binascii.hexlify(o_value).decode() if isinstance(o_value, bytes) else o_value
        u_hex = binascii.hexlify(u_value).decode() if isinstance(u_value, bytes) else u_value
        
        # Find revision
        r_match = re.search(rb'/R\s+(\d+)', data)
        r_value = int(r_match.group(1)) if r_match else 3
        
        # Create the hash
        john_hash = f"{os.path.basename(filename)}:$pdf${r_value}*{o_hex}*{u_hex}"
        return john_hash
    
    except Exception as e:
        return None

def try_all_extraction_methods(filename):
    """Try all extraction methods to get a hash"""
    methods = [
        scan_for_password_patterns,
        generic_pdf_hash
    ]
    
    results = []
    for method in methods:
        result = method(filename)
        if result:
            results.extend(result) if isinstance(result, list) else results.append(result)
    
    return results

def main():
    if len(sys.argv) < 2:
        sys.stderr.write(f"Usage: {sys.argv[0]} <pdf_file>\n")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        sys.stderr.write(f"Error: File not found: {pdf_path}\n")
        sys.exit(1)
    
    # Check if we're in quiet mode (redirecting output)
    quiet_mode = not sys.stdout.isatty()
    
    # Extract hash using all available methods
    results = try_all_extraction_methods(pdf_path)
    
    if not results:
        if not quiet_mode:
            sys.stderr.write("Could not extract hash using any method\n")
            sys.stderr.write("PDF may not be encrypted or uses unusual encryption\n")
            
            # Show test hashes for reference
            sys.stderr.write("\nFor testing, here are some sample PDF hashes:\n")
            for test_hash in create_test_pdf_hashes():
                sys.stderr.write(f"{test_hash}\n")
        
        sys.exit(1)
    
    # If we're in quiet mode, just print the first hashcat hash
    if quiet_mode:
        for method, hash_str, mode in results:
            if method == "hashcat":
                print(hash_str)
                sys.exit(0)
    else:
        # Print all results with instructions
        print(f"Extracted hashes from: {pdf_path}\n")
        
        for method, hash_str, mode in results:
            if method == "hashcat":
                print(f"For hashcat (mode {mode}):")
                print(f"  {hash_str}")
                print(f"  Command: hashcat -m {mode} -a 0 '{hash_str}' wordlist.txt\n")
            elif method == "john":
                print("For John the Ripper:")
                print(f"  {hash_str}")
                print("  Command: john --format=pdf hash.txt\n")
    
    # Also try to create a traditional John format hash
    john_hash = format_as_john_traditional(pdf_path)
    if john_hash and not quiet_mode:
        print("Alternative John format (save to file):")
        print(f"  {john_hash}")
        print("  Command: john --format=pdf hash.txt\n")

if __name__ == "__main__":
    main()
