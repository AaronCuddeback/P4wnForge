#!/usr/bin/env python3
"""
PDF Password Brute Force Tool

This script attempts to crack PDF password protection using brute force.
It allows users to configure:
- Maximum password length
- Character set (digits, lowercase, uppercase, symbols, or combinations)
- Resume from a previous attempt
- Save progress periodically

Usage:
    python pdf_brute_force.py <pdf_file>
"""

import sys
import os
import time
import string
import argparse
import itertools
import json
from datetime import datetime, timedelta

# Try to import various PDF libraries, using the most robust ones first if available
AVAILABLE_LIBRARIES = []

try:
    import pikepdf
    AVAILABLE_LIBRARIES.append(("pikepdf", "Robust PDF library with good encryption support"))
except ImportError:
    pass

try:
    import PyPDF2
    AVAILABLE_LIBRARIES.append(("PyPDF2", "Common PDF library"))
except ImportError:
    pass

try:
    import pypdf
    AVAILABLE_LIBRARIES.append(("pypdf", "Newer version of the PyPDF2 library"))
except ImportError:
    pass

# Check if qpdf command line tool is available
def has_qpdf():
    try:
        import subprocess
        result = subprocess.run(['qpdf', '--version'], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE)
        return result.returncode == 0
    except:
        return False

if has_qpdf():
    AVAILABLE_LIBRARIES.append(("qpdf", "Command line tool for PDF files"))

if not AVAILABLE_LIBRARIES:
    print("Error: No PDF libraries available. Please install at least one of these:")
    print("  pip install pikepdf PyPDF2 pypdf")
    print("  or install qpdf command line tool")
    sys.exit(1)

class PDFBruteForcer:
    def __init__(self, pdf_file, options):
        self.pdf_file = pdf_file
        self.min_length = options.get('min_length', 1)
        self.max_length = options.get('max_length', 8)
        self.character_set = self._get_charset(options.get('charset', 'digits'))
        self.library = options.get('library', AVAILABLE_LIBRARIES[0][0])
        self.save_progress = options.get('save_progress', True)
        self.progress_file = options.get('progress_file', f"{os.path.basename(pdf_file)}.progress")
        self.start_from = options.get('start_from', '')
        self.show_progress_every = options.get('show_progress_every', 1000)
        self.save_progress_every = options.get('save_progress_every', 10000)
        
        self.passwords_tried = 0
        self.start_time = None
        self.current_password = None
        self.found_password = None
        
        # Custom logger - by default uses print, but can be replaced
        self.log = options.get('log_function', print)
        
        # Display initial configuration
        self.log(f"\nPDF Brute Force Configuration:")
        self.log(f"  File: {self.pdf_file}")
        self.log(f"  Length: {self.min_length} to {self.max_length} characters")
        self.log(f"  Character set: {self._describe_charset(options.get('charset', 'digits'))}")
        self.log(f"  Library: {self.library}")
        if self.start_from:
            self.log(f"  Resuming from: '{self.start_from}'")
        self.log(f"  Total possible combinations: {self._calculate_combinations():,}")
        self.log(f"  Progress file: {self.progress_file if self.save_progress else 'Disabled'}")
        self.log("")
        
        self.stopped = False  # Flag to track if process should stop
        
        # Load progress from file if available
        self.load_progress()
    
    def _get_charset(self, charset_name):
        """Get the actual character set based on the name"""
        charsets = {
            'digits': string.digits,
            'lowercase': string.ascii_lowercase,
            'uppercase': string.ascii_uppercase,
            'letters': string.ascii_letters,
            'symbols': string.punctuation,
            'alphanum': string.ascii_letters + string.digits,
            'all': string.ascii_letters + string.digits + string.punctuation
        }
        
        if charset_name in charsets:
            return charsets[charset_name]
        
        # Handle combinations
        combined = ""
        if 'd' in charset_name: combined += string.digits
        if 'l' in charset_name: combined += string.ascii_lowercase
        if 'u' in charset_name: combined += string.ascii_uppercase
        if 's' in charset_name: combined += string.punctuation
        
        return combined if combined else string.digits
    
    def _describe_charset(self, charset_name):
        """Get a human-readable description of the character set"""
        descriptions = {
            'digits': "Digits (0-9)",
            'lowercase': "Lowercase letters (a-z)",
            'uppercase': "Uppercase letters (A-Z)",
            'letters': "All letters (a-z, A-Z)",
            'symbols': "Symbols/special characters",
            'alphanum': "Alphanumeric (a-z, A-Z, 0-9)",
            'all': "All characters (a-z, A-Z, 0-9, symbols)"
        }
        
        if charset_name in descriptions:
            return f"{descriptions[charset_name]} - {len(self._get_charset(charset_name))} characters"
        
        # Handle combinations
        parts = []
        if 'd' in charset_name: parts.append("digits")
        if 'l' in charset_name: parts.append("lowercase")
        if 'u' in charset_name: parts.append("uppercase")
        if 's' in charset_name: parts.append("symbols")
        
        combined = " + ".join(parts)
        return f"Custom set ({combined}) - {len(self._get_charset(charset_name))} characters"
    
    def _calculate_combinations(self):
        """Calculate the total number of possible combinations"""
        charset_size = len(self.character_set)
        total = 0
        for length in range(self.min_length, self.max_length + 1):
            total += charset_size ** length
        return total
    
    def _try_password_pikepdf(self, password):
        """Try to decrypt PDF using pikepdf"""
        try:
            with pikepdf.open(self.pdf_file, password=password) as pdf:
                return True
        except pikepdf.PasswordError:
            return False
        except Exception as e:
            if "not encrypted" in str(e).lower():
                self.log(f"Error: PDF is not encrypted according to pikepdf")
                return False
            self.log(f"pikepdf error: {e}")
            return False
    
    def _try_password_pypdf2(self, password):
        """Try to decrypt PDF using PyPDF2"""
        try:
            with open(self.pdf_file, 'rb') as f:
                pdf = PyPDF2.PdfFileReader(f)
                if pdf.isEncrypted:
                    result = pdf.decrypt(password)
                    return result > 0
                else:
                    self.log(f"Error: PDF is not encrypted according to PyPDF2")
                    return False
        except Exception as e:
            self.log(f"PyPDF2 error: {e}")
            return False
    
    def _try_password_pypdf(self, password):
        """Try to decrypt PDF using pypdf"""
        try:
            with open(self.pdf_file, 'rb') as f:
                pdf = pypdf.PdfReader(f)
                if pdf.is_encrypted:
                    try:
                        pdf.decrypt(password)
                        return True
                    except:
                        return False
                else:
                    self.log(f"Error: PDF is not encrypted according to pypdf")
                    return False
        except Exception as e:
            self.log(f"pypdf error: {e}")
            return False
    
    def _try_password_qpdf(self, password):
        """Try to decrypt PDF using qpdf command line tool"""
        try:
            import subprocess
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp:
                temp_path = temp.name
            
            try:
                cmd = ['qpdf', '--password=' + password, '--decrypt', self.pdf_file, temp_path]
                process = subprocess.run(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                
                # Check if successful
                if process.returncode == 0:
                    return True
                elif "invalid password" in process.stderr.lower():
                    return False
                else:
                    return False
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        except Exception as e:
            self.log(f"qpdf error: {e}")
            return False
    
    def try_password(self, password):
        """Try a password using the selected library"""
        if self.library == "pikepdf":
            return self._try_password_pikepdf(password)
        elif self.library == "PyPDF2":
            return self._try_password_pypdf2(password)
        elif self.library == "pypdf":
            return self._try_password_pypdf(password)
        elif self.library == "qpdf":
            return self._try_password_qpdf(password)
        else:
            # Fallback to trying all available methods
            for lib, _ in AVAILABLE_LIBRARIES:
                if lib == "pikepdf" and self._try_password_pikepdf(password):
                    return True
                elif lib == "PyPDF2" and self._try_password_pypdf2(password):
                    return True
                elif lib == "pypdf" and self._try_password_pypdf(password):
                    return True
                elif lib == "qpdf" and self._try_password_qpdf(password):
                    return True
            return False
    
    def save_current_progress(self):
        """Save the current progress to a file"""
        if not self.save_progress:
            return
        
        try:
            progress_data = {
                'pdf_file': self.pdf_file,
                'passwords_tried': self.passwords_tried,
                'current_password': self.current_password,
                'duration': time.time() - self.start_time if self.start_time else 0,
                'timestamp': datetime.now().isoformat(),
                'charset': ''.join(self.character_set),
                'min_length': self.min_length,
                'max_length': self.max_length
            }
            
            with open(self.progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
        except Exception as e:
            self.log(f"Warning: Could not save progress: {e}")
    
    def load_progress(self):
        """Load progress from a file"""
        if not os.path.exists(self.progress_file):
            return None
        
        try:
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.log(f"Warning: Could not load progress file: {e}")
            return None
    
    def _generate_passwords(self):
        """Generate all possible passwords of the specified lengths"""
        # If we're resuming, find where to start
        resume_from = self.start_from
        resume_active = bool(resume_from)
        
        for length in range(self.min_length, self.max_length + 1):
            for candidate in itertools.product(self.character_set, repeat=length):
                password = ''.join(candidate)
                
                # If we're resuming and haven't reached our starting point yet
                if resume_active:
                    if password == resume_from:
                        resume_active = False  # Found our starting point
                    else:
                        continue  # Skip until we find the starting point
                
                # Check if stopped during generation
                if self.stopped:
                    return
                    
                yield password
    
    def _format_time(self, seconds):
        """Format time duration nicely"""
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        else:
            hours = seconds / 3600
            return f"{hours:.1f} hours"
    
    def _estimate_completion(self, passwords_tried, elapsed_time):
        """Estimate completion time based on current progress"""
        if passwords_tried == 0 or elapsed_time == 0:
            return "unknown"
        
        total_combinations = self._calculate_combinations()
        if self.start_from:
            # Adjust for resumed progress - this is approximate
            progress_pct = passwords_tried / total_combinations
            total_combinations = (total_combinations * (1 - progress_pct)) + passwords_tried
        
        rate = passwords_tried / elapsed_time
        remaining_combinations = total_combinations - passwords_tried
        remaining_seconds = remaining_combinations / rate if rate > 0 else float('inf')
        
        if remaining_seconds > 365 * 24 * 3600:
            years = remaining_seconds / (365 * 24 * 3600)
            return f"~{years:.1f} years"
        elif remaining_seconds > 30 * 24 * 3600:
            months = remaining_seconds / (30 * 24 * 3600)
            return f"~{months:.1f} months"
        elif remaining_seconds > 24 * 3600:
            days = remaining_seconds / (24 * 3600)
            return f"~{days:.1f} days"
        elif remaining_seconds > 3600:
            hours = remaining_seconds / 3600
            return f"~{hours:.1f} hours"
        elif remaining_seconds > 60:
            minutes = remaining_seconds / 60
            return f"~{minutes:.1f} minutes"
        else:
            return f"~{remaining_seconds:.1f} seconds"
    
    def run(self):
        """Run the brute force attack"""
        self.start_time = time.time()
        self.passwords_tried = 0
        last_save_time = time.time()
        estimated_completion = "calculating..."
        
        try:
            for password in self._generate_passwords():
                # Check if we should stop
                if self.stopped:
                    self.log("Process stopped by user.")
                    self.save_current_progress()
                    return False
                    
                self.current_password = password
                self.passwords_tried += 1
                
                # Show progress
                if self.passwords_tried % self.show_progress_every == 0:
                    elapsed = time.time() - self.start_time
                    rate = self.passwords_tried / elapsed if elapsed > 0 else 0
                    
                    # Update the estimated completion time
                    estimated_completion = self._estimate_completion(self.passwords_tried, elapsed)
                    
                    self.log(f"Tried: {self.passwords_tried:,} | Current: {password} | " +
                          f"Rate: {rate:.1f}/sec | Elapsed: {self._format_time(elapsed)} | " +
                          f"Est. completion: {estimated_completion}")
                
                # Save progress periodically
                if self.save_progress and time.time() - last_save_time > 60:
                    self.save_current_progress()
                    last_save_time = time.time()
                
                # Try the password
                if self.try_password(password):
                    self.found_password = password
                    elapsed = time.time() - self.start_time
                    
                    self.log(f"\n{'='*60}")
                    self.log(f"PASSWORD FOUND: '{password}'")
                    self.log(f"Attempts: {self.passwords_tried:,}")
                    self.log(f"Time elapsed: {self._format_time(elapsed)}")
                    self.log(f"Rate: {self.passwords_tried / elapsed:.1f} passwords/second")
                    self.log(f"{'='*60}\n")
                    
                    # Save the found password to a file
                    try:
                        with open(f"{os.path.basename(self.pdf_file)}.password", 'w') as f:
                            f.write(f"Password: {password}\n")
                            f.write(f"Found after {self.passwords_tried:,} attempts\n")
                            f.write(f"Time taken: {self._format_time(elapsed)}\n")
                            f.write(f"Date: {datetime.now().isoformat()}\n")
                        self.log(f"Password saved to {os.path.basename(self.pdf_file)}.password")
                    except Exception as e:
                        self.log(f"Error saving password to file: {e}")
                    
                    return True
            
            self.log(f"Exhausted all combinations. Tried {self.passwords_tried} passwords.")
            return False
            
        except KeyboardInterrupt:
            self.log("Brute force attack interrupted by user.")
            self.save_current_progress()
            return False
        except Exception as e:
            self.log(f"Error during brute force: {str(e)}")
            try:
                self.save_current_progress()
            except:
                pass
            return False

def main():
    # Create argument parser
    parser = argparse.ArgumentParser(description="PDF Password Brute Force Tool")
    parser.add_argument("pdf_file", help="Path to the encrypted PDF file")
    parser.add_argument("--min-length", type=int, default=1, help="Minimum password length (default: 1)")
    parser.add_argument("--max-length", type=int, default=8, help="Maximum password length (default: 8)")
    parser.add_argument("--charset", default="digits", 
                       help="Character set to use: digits, lowercase, uppercase, letters, alphanum, all, " +
                            "or any combination of d (digits), l (lowercase), u (uppercase), s (symbols)")
    parser.add_argument("--start-from", default="", help="Resume from this password")
    parser.add_argument("--library", default=AVAILABLE_LIBRARIES[0][0] if AVAILABLE_LIBRARIES else None,
                       help=f"Library to use: {', '.join(lib for lib, _ in AVAILABLE_LIBRARIES)}")
    parser.add_argument("--no-save-progress", action="store_true", help="Disable progress saving")
    parser.add_argument("--progress-file", help="Custom progress file name")
    parser.add_argument("--show-available-libraries", action="store_true", help="Show available libraries and exit")
    parser.add_argument("--verbose", action="store_true", help="Show more detailed progress")
    
    args = parser.parse_args()
    
    # Show available libraries if requested
    if args.show_available_libraries:
        print("\nAvailable PDF libraries:")
        for lib, desc in AVAILABLE_LIBRARIES:
            print(f"  {lib}: {desc}")
        sys.exit(0)
    
    # Check if the PDF file exists
    if not os.path.exists(args.pdf_file):
        print(f"Error: File not found: {args.pdf_file}")
        sys.exit(1)
    
    # Check if the library is valid
    if args.library and args.library not in [lib for lib, _ in AVAILABLE_LIBRARIES]:
        print(f"Error: Invalid library '{args.library}'. Available libraries:")
        for lib, desc in AVAILABLE_LIBRARIES:
            print(f"  {lib}: {desc}")
        sys.exit(1)
    
    # Setup options
    options = {
        'min_length': args.min_length,
        'max_length': args.max_length,
        'charset': args.charset,
        'start_from': args.start_from,
        'library': args.library,
        'save_progress': not args.no_save_progress,
        'show_progress_every': 100 if args.verbose else 1000
    }
    
    if args.progress_file:
        options['progress_file'] = args.progress_file
    
    # Create and run the brute forcer
    brute_forcer = PDFBruteForcer(args.pdf_file, options)
    
    print("\nStarting brute force attack...")
    print("Press Ctrl+C to stop at any time (progress will be saved)")
    brute_forcer.run()

if __name__ == "__main__":
    main()
