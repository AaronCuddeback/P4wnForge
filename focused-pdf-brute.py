#!/usr/bin/env python3
"""
Focused PDF Password Tester that tries multiple libraries and methods
"""
import sys
import os
import time

def try_with_pypdf2(pdf_file, password):
    """Try to open PDF with PyPDF2"""
    try:
        from PyPDF2 import PdfFileReader
        with open(pdf_file, 'rb') as f:
            pdf = PdfFileReader(f)
            if pdf.isEncrypted:
                result = pdf.decrypt(password)
                return result > 0
            else:
                print("PDF is not encrypted according to PyPDF2")
                return False
    except Exception as e:
        print(f"PyPDF2 error: {e}")
        return False

def try_with_pypdf(pdf_file, password):
    """Try to open PDF with newer pypdf library"""
    try:
        import pypdf
        with open(pdf_file, 'rb') as f:
            pdf = pypdf.PdfReader(f)
            if pdf.is_encrypted:
                try:
                    pdf.decrypt(password)
                    # If we get here without exception, password worked
                    return True
                except pypdf.errors.PdfReadError:
                    return False
            else:
                print("PDF is not encrypted according to pypdf")
                return False
    except ImportError:
        print("pypdf library not installed")
        return False
    except Exception as e:
        print(f"pypdf error: {e}")
        return False

def try_with_pikepdf(pdf_file, password):
    """Try to open PDF with pikepdf library"""
    try:
        import pikepdf
        try:
            # Try to open with password
            pdf = pikepdf.open(pdf_file, password=password)
            pdf.close()
            return True
        except pikepdf.PasswordError:
            return False
        except Exception as e:
            print(f"pikepdf error: {e}")
            return False
    except ImportError:
        print("pikepdf library not installed")
        return False

def try_with_qpdf(pdf_file, password):
    """Try to open PDF with qpdf command line tool"""
    try:
        import subprocess
        import tempfile
        
        # Create a temporary output file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp:
            temp_path = temp.name
        
        try:
            # Try to decrypt with qpdf
            cmd = ['qpdf', '--password=' + password, '--decrypt', pdf_file, temp_path]
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            _, stderr = process.communicate()
            
            # Check if it worked
            if process.returncode == 0:
                return True
            elif "invalid password" in stderr.lower():
                return False
            else:
                print(f"QPDF returned: {stderr}")
                return False
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    except Exception as e:
        print(f"QPDF error: {e}")
        return False

def try_password_with_all_methods(pdf_file, password):
    """Try a password using all available methods"""
    methods = [
        ("PyPDF2", try_with_pypdf2),
        ("pypdf", try_with_pypdf),
        ("pikepdf", try_with_pikepdf),
        ("qpdf", try_with_qpdf)
    ]
    
    results = []
    for name, method in methods:
        result = method(pdf_file, password)
        results.append((name, result))
        if result:
            print(f"SUCCESS: Password '{password}' works with {name}")
        else:
            print(f"FAILED: Password '{password}' does not work with {name}")
    
    # Return True if any method succeeded
    return any(result for _, result in results)

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <pdf_file> [specific_password]")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    if not os.path.exists(pdf_file):
        print(f"File not found: {pdf_file}")
        sys.exit(1)
    
    # If a specific password is provided, try only that
    if len(sys.argv) >= 3:
        specific_password = sys.argv[2]
        print(f"Testing specific password: '{specific_password}'")
        if try_password_with_all_methods(pdf_file, specific_password):
            print(f"\nPassword confirmed: '{specific_password}'")
            sys.exit(0)
        else:
            print(f"\nPassword '{specific_password}' does not work with any method")
            choice = input("Continue with additional tests? (y/n): ")
            if not choice.lower().startswith('y'):
                sys.exit(1)
    
    # Define some patterns to try
    patterns = [
        # Empty password
        "",
        # The specific password you mentioned
        "5678",
        # Common variations
        "5678 ",  # With trailing space
        " 5678",  # With leading space
        "\x005678",  # With null byte prefix
        "5678\x00",  # With null byte suffix
        # Other common numeric patterns
        "1234", "0000", "9999", "0000", "1111", "2222", "3333", "4444",
        "5555", "6666", "7777", "8888", "9999", "1212", "1313", "1414",
        "1515", "1616", "1717", "1818", "1919", "2020", "2121", "2323",
        "2424", "2525", "2626", "2727", "2828", "2929"
    ]
    
    print(f"\nTesting {len(patterns)} password patterns...")
    for password in patterns:
        print(f"\nTrying: '{password}' ({' '.join(hex(ord(c))[2:] for c in password)})")
        if try_password_with_all_methods(pdf_file, password):
            print(f"\nPassword found: '{password}'")
            return
    
    # Try additional numeric combinations
    print("\nTrying 4-digit numeric combinations (0000-9999)...")
    found = False
    start_time = time.time()
    count = 0
    
    for i in range(10000):
        count += 1
        password = f"{i:04d}"
        
        if count % 500 == 0:
            elapsed = time.time() - start_time
            print(f"Tried {count} passwords in {elapsed:.2f} seconds ({count/elapsed:.2f} attempts/sec)")
            print(f"Current: {password}")
        
        # Try with PyPDF2 first (faster)
        if try_with_pypdf2(pdf_file, password):
            # If it works, verify with other methods
            print(f"\nPotential match found: '{password}' - Verifying with other methods...")
            if try_password_with_all_methods(pdf_file, password):
                print(f"\nPassword confirmed: '{password}'")
                found = True
                break
    
    if not found:
        print("\nPassword not found among 4-digit combinations")
        
        # Try a few 8-digit combinations that might be years
        years = []
        current_year = 2025
        for year in range(1980, current_year + 1):
            years.append(str(year))
            years.append(f"{year}0101")  # January 1st
            years.append(f"{year}1231")  # December 31st
        
        print(f"\nTrying {len(years)} date-based passwords...")
        for password in years:
            if try_password_with_all_methods(pdf_file, password):
                print(f"\nPassword found: '{password}'")
                found = True
                break
    
    if not found:
        print("\nAll attempts failed. The PDF might use a different encryption method or password format.")
        print("Consider trying specialized PDF password recovery tools.")

if __name__ == "__main__":
    main()
