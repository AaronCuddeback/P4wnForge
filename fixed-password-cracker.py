import sys
import os
import subprocess
import platform
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import requests
import zipfile
import shutil

# Ensure you have installed PyMuPDF (pip install PyMuPDF)
import fitz  # PyMuPDF

class PasswordCrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Password Cracker Tool")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # Initialize variables
        self.hashcat_path = ""
        self.password_list_path = tk.StringVar()
        self.target_file_path = tk.StringVar()
        # PDF version combobox remains for interface consistency
        self.pdf_version_combobox = None
        
        self.output_text = None
        self.current_tab = None
        
        # Create main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs
        self.tab_control = ttk.Notebook(main_frame)
        
        self.office_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.office_tab, text="Office Documents")
        
        self.pdf_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.pdf_tab, text="PDF Files")
        
        self.hash_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.hash_tab, text="NTLM Hash")
        
        self.tab_control.pack(fill=tk.BOTH, expand=True)
        
        # Set up each tab's content
        self.setup_office_tab()
        self.setup_pdf_tab()
        self.setup_hash_tab()
        
        # Bottom frame for common controls
        bottom_frame = ttk.Frame(main_frame, padding="10")
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        ttk.Label(bottom_frame, text="Password List:").grid(column=0, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(bottom_frame, textvariable=self.password_list_path, width=50).grid(column=1, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Button(bottom_frame, text="Browse", command=self.browse_password_list).grid(column=2, row=0, sticky=tk.W, padx=5, pady=5)
        
        # Output area
        ttk.Label(main_frame, text="Output:").pack(anchor=tk.W, padx=10)
        output_frame = ttk.Frame(main_frame, padding="5")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.output_text = tk.Text(output_frame, height=10, width=80, wrap=tk.WORD)
        self.output_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.output_text.tag_configure("password_found", foreground="green", font=("Helvetica", 10, "bold"))
        
        scrollbar = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.output_text.yview)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        self.output_text.config(yscrollcommand=scrollbar.set)
        
        # Check for required tools
        self.check_hashcat()
        self.check_john_tools()
    
    def setup_office_tab(self):
        frame = ttk.LabelFrame(self.office_tab, text="Microsoft Office Document Cracking", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(frame, text="Office Document:").grid(column=0, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.target_file_path, width=50).grid(column=1, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Button(frame, text="Browse", command=lambda: self.browse_file([("Word Documents", "*.docx *.doc"),
                                                                             ("Excel Documents", "*.xlsx *.xls"),
                                                                             ("All Files", "*.*")])).grid(column=2, row=0, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(frame, text="Office Version:").grid(column=0, row=1, sticky=tk.W, padx=5, pady=5)
        office_version = ttk.Combobox(frame, values=["Office 2007", "Office 2010", "Office 2013", "Office 2016", "Office 2019", "Office 365"])
        office_version.grid(column=1, row=1, sticky=tk.W, padx=5, pady=5)
        office_version.current(3)  # Default to Office 2016
        
        ttk.Button(frame, text="Start Cracking", command=lambda: self.start_cracking("office")).grid(column=1, row=2, sticky=tk.E, padx=5, pady=20)
    
    def setup_pdf_tab(self):
        frame = ttk.LabelFrame(self.pdf_tab, text="PDF Document Cracking", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(frame, text="PDF Document:").grid(column=0, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.target_file_path, width=50).grid(column=1, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Button(frame, text="Browse", command=lambda: self.browse_file([("PDF Files", "*.pdf"), ("All Files", "*.*")])).grid(column=2, row=0, sticky=tk.W, padx=5, pady=5)
        
        # PDF version selection remains for interface consistency
        ttk.Label(frame, text="PDF Version:").grid(column=0, row=1, sticky=tk.W, padx=5, pady=5)
        self.pdf_version_combobox = ttk.Combobox(frame, values=[
            "Acrobat 5.0 and later (PDF 1.4)",
            "Acrobat 6.0 and later (PDF 1.5)",
            "Acrobat 7.0 and later (PDF 1.6)",
            "Acrobat 9.0 and later (PDF 1.7)"
        ])
        self.pdf_version_combobox.grid(column=1, row=1, sticky=tk.W, padx=5, pady=5)
        self.pdf_version_combobox.current(3)
        
        ttk.Button(frame, text="Start Cracking", command=lambda: self.start_cracking("pdf")).grid(column=1, row=2, sticky=tk.E, padx=5, pady=20)
    
    def setup_hash_tab(self):
        frame = ttk.LabelFrame(self.hash_tab, text="NTLM Hash Cracking", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(frame, text="Hash File:").grid(column=0, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.target_file_path, width=50).grid(column=1, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Button(frame, text="Browse", command=lambda: self.browse_file([("Hash Files", "*.hash"), ("Text Files", "*.txt"), ("All Files", "*.*")])).grid(column=2, row=0, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(frame, text="Hash Type:").grid(column=0, row=1, sticky=tk.W, padx=5, pady=5)
        hash_type = ttk.Combobox(frame, values=["NTLMv2", "NTLM", "NetNTLMv2", "NetNTLM"])
        hash_type.grid(column=1, row=1, sticky=tk.W, padx=5, pady=5)
        hash_type.current(0)
        
        ttk.Button(frame, text="Start Cracking", command=lambda: self.start_cracking("hash")).grid(column=1, row=2, sticky=tk.E, padx=5, pady=20)
    
    def browse_password_list(self):
        filename = filedialog.askopenfilename(
            title="Select Password List",
            filetypes=[("Text Files", "*.txt"), ("Word Lists", "*.dict"), ("All Files", "*.*")]
        )
        if filename:
            self.password_list_path.set(filename)
    
    def browse_file(self, filetypes):
        filename = filedialog.askopenfilename(
            title="Select Target File",
            filetypes=filetypes
        )
        if filename:
            self.target_file_path.set(filename)
            self.current_tab = self.tab_control.tab(self.tab_control.select(), "text").lower()
    
    def find_extraction_tool(self, tool_name):
        """Search for extraction tools (office2john.py or pdf2john.py) in common locations."""
        search_paths = [
            os.path.dirname(self.hashcat_path) if self.hashcat_path else "",
            os.getcwd(),
            os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'John the Ripper', 'run'),
            os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), 'John the Ripper', 'run'),
            os.path.expanduser("~/john/run"),
            "./run",
            "."
        ]
        for path in os.environ.get('PATH', '').split(os.pathsep):
            if path and path not in search_paths:
                search_paths.append(path)
        
        john_path = self.find_john_the_ripper()
        if john_path:
            john_dir = os.path.dirname(john_path)
            if john_dir not in search_paths:
                search_paths.append(john_dir)
            run_dir = os.path.join(john_dir, "run")
            if os.path.exists(run_dir) and run_dir not in search_paths:
                search_paths.append(run_dir)
        
        for path in search_paths:
            if not path:
                continue
            tool_path = os.path.join(path, tool_name)
            if os.path.exists(tool_path):
                return tool_path
        return None
    
    def check_john_tools(self):
        self.log_output("Checking for hash extraction tools...")
        search_paths = [
            os.path.dirname(self.hashcat_path) if self.hashcat_path else "",
            os.getcwd(),
            os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'John the Ripper', 'run'),
            os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), 'John the Ripper', 'run'),
            os.path.expanduser("~/john/run"),
            "./run"
        ]
        for path in os.environ.get('PATH', '').split(os.pathsep):
            if path and path not in search_paths:
                search_paths.append(path)
        
        office2john_found = False
        pdf2john_found = False
        
        for path in search_paths:
            if not path:
                continue
            office2john_path = os.path.join(path, "office2john.py")
            pdf2john_path = os.path.join(path, "pdf2john.py")
            if os.path.exists(office2john_path) and not office2john_found:
                self.log_output(f"✓ Found office2john.py at: {office2john_path}")
                office2john_found = True
            if os.path.exists(pdf2john_path) and not pdf2john_found:
                self.log_output(f"✓ Found pdf2john.py at: {pdf2john_path}")
                pdf2john_found = True
            if office2john_found and pdf2john_found:
                break
        
        if not office2john_found:
            self.log_output("✗ office2john.py not found. Office document cracking may be less effective.")
            self.log_output("  Download from: https://raw.githubusercontent.com/openwall/john/bleeding-jumbo/run/office2john.py")
        if not pdf2john_found:
            self.log_output("✗ pdf2john.py not found. PDF cracking may be less effective.")
            self.log_output("  Download from: https://raw.githubusercontent.com/openwall/john/bleeding-jumbo/run/pdf2john.py")
        self.log_output("Hash extraction tools check completed.")
    
    def find_john_the_ripper(self):
        try:
            result = subprocess.run(["john", "--version"], capture_output=True, text=True)
            if "John the Ripper" in result.stdout or "John the Ripper" in result.stderr:
                self.log_output("Found John the Ripper in PATH")
                return "john"
        except FileNotFoundError:
            common_paths = [
                os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'John the Ripper'),
                os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), 'John the Ripper'),
                os.path.expanduser("~/john"),
                "./john"
            ]
            for path in common_paths:
                exe_path = os.path.join(path, "john.exe" if sys.platform == "win32" else "john")
                if os.path.exists(exe_path):
                    self.log_output(f"Found John the Ripper at: {exe_path}")
                    return exe_path
            self.log_output("John the Ripper not found")
            return None
        return "john"
    
    def check_hashcat(self):
        self.log_output("Checking for hashcat installation...")
        try:
            result = subprocess.run(["hashcat", "--version"], capture_output=True, text=True)
            version = result.stdout.strip()
            self.hashcat_path = "hashcat"
            self.log_output(f"Hashcat found: {version}")
            return True
        except FileNotFoundError:
            self.log_output("Hashcat not found in system PATH.")
            common_paths = [
                os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'hashcat'),
                os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), 'hashcat'),
                os.path.expanduser("~/hashcat"),
                "./hashcat"
            ]
            for path in common_paths:
                exe_path = os.path.join(path, "hashcat.exe")
                if os.path.exists(exe_path):
                    self.hashcat_path = exe_path
                    self.log_output(f"Hashcat found at: {exe_path}")
                    return True
            self.log_output("Hashcat not found. Please install hashcat from https://hashcat.net/hashcat/")
            return False
    
    def install_hashcat(self):
        # Installation code omitted for brevity.
        pass
    
    def start_cracking(self, file_type):
        if not self.password_list_path.get():
            messagebox.showerror("Error", "Please select a password list file")
            return
        
        if not self.target_file_path.get():
            messagebox.showerror("Error", "Please select a target file to crack")
            return
        
        if not self.hashcat_path and not self.check_hashcat():
            messagebox.showerror("Error", "Hashcat is required but not installed")
            return
        
        thread = threading.Thread(target=self._run_cracking_process, args=(file_type,))
        thread.daemon = True
        thread.start()
    
    def _run_cracking_process(self, file_type):
        self.log_output(f"Starting {file_type} password cracking...")
        self.log_output(f"Target file: {self.target_file_path.get()}")
        self.log_output(f"Password list: {self.password_list_path.get()}")
        
        if file_type == "office":
            self._crack_office()
        elif file_type == "pdf":
            self._crack_pdf()
        elif file_type == "hash":
            self._crack_hash()
    
    def _crack_office(self):
        target_file = self.target_file_path.get()
        hash_file = os.path.join(os.path.dirname(target_file), "office_hash.txt")
        # Default mode in case extraction fails
        office_hash_mode = "9600"
        command = [self.hashcat_path if os.path.dirname(self.hashcat_path)
                   else ("hashcat.exe" if sys.platform=="win32" else "hashcat")]
        try:
            self.log_output("Extracting hash from Office document...")
            office2john_path = self.find_extraction_tool("office2john.py")
            if office2john_path:
                self.log_output(f"Using office2john.py at {office2john_path} to extract hash...")
                extract_cmd = [sys.executable, office2john_path, target_file]
                result = subprocess.run(extract_cmd, capture_output=True, text=True)
                raw_output = result.stdout.strip()
                self.log_output(f"Raw hash output: {raw_output[:50]}...")
                if "$office$" in raw_output:
                    hash_part = raw_output.split(":", 1)[1] if ":" in raw_output else raw_output
                    if "*2013*" in hash_part:
                        office_hash_mode = "9600"
                    elif "*2010*" in hash_part:
                        office_hash_mode = "9500"
                    elif "*2007*" in hash_part:
                        office_hash_mode = "9400"
                    else:
                        office_hash_mode = "9600"
                    with open(hash_file, 'w') as f:
                        f.write(hash_part)
                    self.log_output(f"Hash extracted to {hash_file} using mode {office_hash_mode}")
                    command.extend(["-m", office_hash_mode])
                else:
                    self.log_output("Hash not in expected format. Using direct hashcat method...")
                    command.extend(["-m", "9600", "--username", "--force"])
            else:
                self.log_output("office2john.py not found. Using direct hashcat method...")
                command.extend(["-m", "9600", "--username", "--force"])
        except Exception as e:
            self.log_output(f"Error extracting hash: {str(e)}")
            command.extend(["-m", "9600", "--username", "--force"])
        
        if os.path.exists(hash_file) and os.path.getsize(hash_file) > 0:
            command.extend(["-a", "0", hash_file, self.password_list_path.get()])
        else:
            self.log_output("No hash extracted. Attempting direct cracking...")
            command.extend(["-m", "9600", "-a", "0", target_file, self.password_list_path.get(), "--force"])
        
        outfile_path = os.path.join(os.path.dirname(self.target_file_path.get()), "cracked_password.txt").replace('\\', '/')
        command.extend(["--outfile", outfile_path])
        if "--force" not in command:
            command.append("--force")
        self.log_output(f"Executing command: {' '.join(command)}")
        hashcat_dir = os.path.dirname(self.hashcat_path) if os.path.dirname(self.hashcat_path) else None
        
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=hashcat_dir)
            for line in iter(process.stdout.readline, ''):
                self.log_output(line.strip())
            process.wait()
            # Run --show command to retrieve the password
            if os.path.exists(hash_file) and os.path.getsize(hash_file) > 0:
                show_target = hash_file
            else:
                show_target = target_file
            show_cmd = [self.hashcat_path, "-m", office_hash_mode, "--show", show_target]
            self.log_output(f"Executing show command: {' '.join(show_cmd)}")
            show_result = subprocess.run(show_cmd, capture_output=True, text=True, cwd=hashcat_dir)
            self.log_output("Show command output:")
            self.log_output(show_result.stdout)
            recovered_password = None
            for line in show_result.stdout.splitlines():
                if ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1 and parts[1].strip():
                        recovered_password = parts[1].strip()
                        break
            if recovered_password:
                self.log_output("Password cracking completed successfully!", is_password=True)
                self.log_output(f"PASSWORD FOUND: {recovered_password}", is_password=True)
            else:
                self.log_output("Password found but could not parse output.", is_password=True)
        except Exception as e:
            self.log_output(f"Error executing hashcat command: {str(e)}")
            self.log_output("Command that failed: " + " ".join(command))
    
    def _crack_pdf(self):
        # PDF cracking method using PyMuPDF (fitz)
        pdf_path = self.target_file_path.get().strip()
        wordlist_path = self.password_list_path.get().strip()
        
        if not pdf_path or not wordlist_path:
            messagebox.showerror("Error", "Please select a PDF file and a wordlist!")
            return
        
        try:
            with open(wordlist_path, "r", encoding="latin-1") as f:
                passwords = f.readlines()
            
            pdf_doc = fitz.open(pdf_path)
            found = False
            for password in passwords:
                password = password.strip()
                self.log_output(f"Trying password: {password}")
                if pdf_doc.authenticate(password):
                    messagebox.showinfo("Success!", f"Password found: {password}")
                    self.log_output(f"PDF password cracking completed successfully! PASSWORD FOUND: {password}", is_password=True)
                    found = True
                    break
            if not found:
                messagebox.showerror("Failed", "No password in dictionary matched!")
                self.log_output("No password in dictionary matched!")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")
            self.log_output(f"Error in PDF cracking: {e}")
    
    def _crack_hash(self):
        target_file = self.target_file_path.get()
        command = [self.hashcat_path if os.path.dirname(self.hashcat_path)
                   else ("hashcat.exe" if sys.platform=="win32" else "hashcat")]
        command.extend(["-m", "5600", "-a", "0", target_file, self.password_list_path.get()])
        outfile_path = os.path.join(os.path.dirname(self.target_file_path.get()), "cracked_password.txt").replace('\\', '/')
        command.extend(["--outfile", outfile_path])
        if "--force" not in command:
            command.append("--force")
        self.log_output(f"Executing command: {' '.join(command)}")
        hashcat_dir = os.path.dirname(self.hashcat_path) if os.path.dirname(self.hashcat_path) else None
        
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=hashcat_dir)
            for line in iter(process.stdout.readline, ''):
                self.log_output(line.strip())
            process.wait()
            self.log_output("Password cracking completed, check outfile if not displayed here.")
        except Exception as e:
            self.log_output(f"Error executing hashcat command: {str(e)}")
    
    def _save_cracked_password(self, target_file, password):
        try:
            save_path = os.path.join(os.path.dirname(target_file), "cracked_password.txt")
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(f"{target_file}:{password}")
        except Exception as e:
            self.log_output("Note: Couldn't save password to file, but it was found!")
    
    def log_output(self, message, is_password=False):
        if self.output_text:
            if is_password:
                self.output_text.insert(tk.END, message + "\n", "password_found")
            else:
                self.output_text.insert(tk.END, message + "\n")
            self.output_text.see(tk.END)
            self.root.update_idletasks()

def main():
    root = tk.Tk()
    app = PasswordCrackerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
