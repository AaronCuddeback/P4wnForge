import sys
import os
import subprocess
import platform
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import requests
import zipfile
import shutil
from PIL import Image, ImageTk
import webbrowser
import json
import time
import paramiko
from paramiko import SSHClient
from stat import S_ISDIR
import re

# Ensure you have installed PyMuPDF (pip install PyMuPDF)
import fitz  # PyMuPDF

# Import PDFBruteForcer from pdfbrute.py
try:
    from pdfbrute import PDFBruteForcer, AVAILABLE_LIBRARIES
except ImportError:
    # Define fallback if import fails
    AVAILABLE_LIBRARIES = []
    PDFBruteForcer = None

# Custom Combobox class to fix the selection issue
class FixedCombobox(ttk.Combobox):
    """A custom Combobox that fixes selection color issues"""
    def __init__(self, master=None, is_dark_mode_var=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config(state="readonly")  # Always use readonly state
        self.is_dark_mode_var = is_dark_mode_var  # Store reference to dark mode variable
        
        # Bind virtual event to post-select event
        self.bind("<<ComboboxSelected>>", self._on_select)
        
        # Initialize with proper styling
        self._fix_dropdown_style()
        
        # Bind dropdown events
        self.bind("<Map>", self._on_map)
    
    def _fix_dropdown_style(self):
        """Apply direct styling to the combobox dropdown"""
        style = ttk.Style()
        
        # Check if we're in dark mode
        is_dark = False
        if hasattr(self, 'is_dark_mode_var') and self.is_dark_mode_var is not None:
            is_dark = self.is_dark_mode_var.get()
        
        if is_dark:
            # Dark mode styling
            style.map("TCombobox", 
                     selectbackground=[('readonly', '#3E3E3E')],
                     selectforeground=[('readonly', '#FFFFFF')])
            
            # Use more direct approach to configure the dropdown
            self.tk.eval("""
                option add *TCombobox*Listbox.background #3E3E3E
                option add *TCombobox*Listbox.foreground #FFFFFF
                option add *TCombobox*Listbox.selectBackground #4E4E4E
                option add *TCombobox*Listbox.selectForeground #FFFFFF
            """)
        else:
            # Light mode styling
            style.map("TCombobox", 
                     selectbackground=[('readonly', '#FFFFFF')],
                     selectforeground=[('readonly', '#000000')])
            
            # Use more direct approach to configure the dropdown
            self.tk.eval("""
                option add *TCombobox*Listbox.background white
                option add *TCombobox*Listbox.foreground black
                option add *TCombobox*Listbox.selectBackground #0078D7
                option add *TCombobox*Listbox.selectForeground black
            """)
        
        self.config(exportselection=0)
    
    def _on_select(self, event):
        """Ensure proper styling after selection"""
        self.selection_clear()
    
    def _on_map(self, event):
        """Fix styling when dropdown is shown"""
        self._fix_dropdown_style()
    
    def update_theme(self, is_dark):
        """Update the combobox styling based on the current theme"""
        if is_dark:
            self.configure(foreground='white')
        else:
            self.configure(foreground='black')
        self._fix_dropdown_style()

class PasswordCrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("P4wnForge Password Recovery Tool")
        self.root.geometry("950x700")
        self.root.minsize(800, 600)
        
        # Set application icon
        try:
            if platform.system() == "Windows":
                icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "P4wnForge_icon.ico")
                if os.path.exists(icon_path):
                    self.root.iconbitmap(icon_path)
            else:
                # For non-Windows platforms, use webp
                icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "P4wnForge.webp")
                if os.path.exists(icon_path):
                    icon_img = Image.open(icon_path)
                    icon_photo = ImageTk.PhotoImage(icon_img)
                    self.root.iconphoto(True, icon_photo)
        except Exception as e:
            print(f"Error setting application icon: {e}")
        
        # Default configuration
        self.config = {
            'window_width': 950,
            'window_height': 700,
            'dark_mode': False, 
            'sash_position': 250  # Lower position gives more space to output area
        }
        
        # Load configuration before initializing UI elements
        # This ensures config values are available for initial states
        self.config_file = None
        self.load_window_config()
        
        # Initialize variables with values from loaded config
        self.is_dark_mode = tk.BooleanVar(value=self.config.get('dark_mode', False))
        self.target_file_path = tk.StringVar()
        self.password_list_path = tk.StringVar()
        self.bruteforce_length = tk.IntVar(value=8)  # Default bruteforce length is 8
        
        # Bruteforce character set options
        self.use_lowercase = tk.BooleanVar(value=True)
        self.use_uppercase = tk.BooleanVar(value=True)
        self.use_digits = tk.BooleanVar(value=True)
        self.use_special = tk.BooleanVar(value=True)
        
        self.ssh_host = tk.StringVar()
        self.ssh_port = tk.StringVar(value="22")
        self.ssh_username = tk.StringVar()
        self.ssh_password = tk.StringVar()
        self.ssh_current_dir = tk.StringVar(value="/")
        self.ssh_session_name = tk.StringVar()
        self.ssh_remember_password = tk.BooleanVar(value=False)
        
        # Initialize paths and states
        self.hashcat_path = ""
        
        # SSH connection objects
        self.ssh_client = None
        self.sftp_client = None
        
        # Flags and state
        self.is_cracking = False
        self.cracking_process = None
        
        # Dictionary management
        self.dictionary_files = []
        
        # Application Style
        self.style = ttk.Style()
        
        # Create a top toolbar with the dark mode toggle
        toolbar_frame = ttk.Frame(self.root)
        toolbar_frame.pack(fill=tk.X, side=tk.TOP, padx=5, pady=5)
        
        # Add a standard dark mode checkbox to the right side of the toolbar
        self.dark_mode_cb = ttk.Checkbutton(
            toolbar_frame, 
            text="Dark Mode", 
            variable=self.is_dark_mode,
            command=self._on_dark_mode_changed,
            style='TCheckbutton'
        )
        self.dark_mode_cb.pack(side=tk.RIGHT, padx=10)
        
        # Create main layout with PanedWindow
        self.main_paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True)
        
        # Upper part contains the tab control
        self.tab_control = ttk.Notebook(self.main_paned)
        self.main_paned.add(self.tab_control, weight=1)  # Equal weight for top panel
        
        # Create tabs
        self.office_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.office_tab, text="Office Documents")
        
        self.pdf_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.pdf_tab, text="PDF Documents")
        
        self.hash_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.hash_tab, text="NTLM Hash")
        
        self.dictionary_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.dictionary_tab, text="Dictionary Manager")
        
        # Add SSH tab
        self.ssh_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.ssh_tab, text="SSH File Browser")
        
        # Add About tab
        self.about_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.about_tab, text="About")
        
        # Set up each tab's content
        self.setup_office_tab()
        self.setup_pdf_tab()
        self.setup_hash_tab()
        self.setup_dictionary_tab()
        self.setup_ssh_tab()
        self.setup_about_tab()
        
        # Lower part contains password list selector and output
        self.lower_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.lower_frame, weight=1)  # Equal weight to top panel
        
        # Password list selector in the lower frame
        password_frame = ttk.Frame(self.lower_frame, padding="5")
        password_frame.pack(fill=tk.X, side=tk.TOP, pady=5)
        
        ttk.Label(password_frame, text="Password List:").grid(column=0, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(password_frame, textvariable=self.password_list_path, width=50).grid(column=1, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Button(password_frame, text="Browse", command=self.browse_password_list).grid(column=2, row=0, sticky=tk.W, padx=5, pady=5)
        
        # Output area in the lower frame
        self.output_frame = ttk.LabelFrame(self.lower_frame, text="Output")
        self.output_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Output controls
        output_controls = ttk.Frame(self.output_frame, padding="5")
        output_controls.pack(fill=tk.X, side=tk.TOP)
        
        clear_button = ttk.Button(output_controls, text="Clear Output", command=self.clear_output)
        clear_button.pack(side=tk.LEFT, padx=5)
        
        save_button = ttk.Button(output_controls, text="Save Output", command=self.save_output)
        save_button.pack(side=tk.LEFT, padx=5)
        
        # Status button in output controls - assign command to send status
        status_button = ttk.Button(output_controls, text="Status", command=self.send_status_command)
        status_button.pack(side=tk.LEFT, padx=5)
        
        # Text widget inside a frame with scrollbar
        text_frame = ttk.Frame(self.output_frame, padding="5")
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.output_text = tk.Text(text_frame, height=10, width=80, wrap=tk.WORD)
        self.output_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.output_text.tag_configure("password_found", foreground="green", font=("Helvetica", 10, "bold"))
        
        # Add initial text to show the output is working
        self.output_text.insert(tk.END, "P4wnForge initialized - ready to recover passwords\n")
        
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.output_text.yview)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        self.output_text.config(yscrollcommand=scrollbar.set)
        
        # Add tab change event to toggle output visibility
        self.tab_control.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        
        # Set active tab from config if available
        if 'active_tab' in self.config:
            try:
                self.tab_control.select(self.config['active_tab'])
            except Exception:
                # If the tab index is invalid, just use the first tab
                self.tab_control.select(0)
        
        # Apply theme based on dark mode setting
        self.update_theme()
        
        # Set up window event listeners
        self.root.bind("<Configure>", self._on_window_configure)
        self.main_paned.bind("<ButtonRelease-1>", self._on_sash_moved)
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        
        # Now that all widgets are created, set initial sash position
        self.root.after(100, self._set_initial_sash_position)
        
        # Load saved dictionaries
        self.load_dictionary_list()
        
        # Load SSH sessions
        self.load_ssh_sessions()
        
        # Check for hashcat and other prerequisites
        self.check_hashcat()
        self.check_john_tools()
        
        # Set a much larger output area by default - this runs after all initialization
        self.root.after(1000, self.ensure_large_output_area)

    def ensure_large_output_area(self):
        """Forces the output area to take up at least 60% of the window height"""
        if not hasattr(self, 'main_paned'):
            return
            
        try:
            # Calculate a position that gives at least 60% to the output area
            window_height = self.root.winfo_height()
            # The lower this number, the more space for the output area
            target_pos = int(window_height * 0.4)  # 40% for top, 60% for bottom
            
            # Don't go too small for small windows
            if target_pos < 200:
                target_pos = 200
                
            # Set the sash position directly
            self.main_paned.sashpos(0, target_pos)
            
            # Save this position in the config
            self.config['sash_position'] = target_pos
            self.save_window_config()
        except Exception:
            pass

    def _set_initial_sash_position(self):
        """Set the initial sash position from config or reasonable default"""
        if hasattr(self, 'main_paned'):
            try:
                # Make sure paned window has sashes before trying to position them
                panes = self.main_paned.panes()
                if len(panes) < 2:
                    return  # Not enough panes to have a sash
                
                # Check if we have a valid sash position in config
                if 'sash_position' in self.config and self.config['sash_position'] > 100:
                    # A direct immediate set, plus a delayed set to ensure it takes effect
                    sash_pos = self.config['sash_position']
                    
                    # Set immediately 
                    self.main_paned.sashpos(0, sash_pos)
                    
                    # Then schedule another set after a short delay to ensure it takes effect
                    # This ensures the window is fully rendered before setting the position
                    self.root.after(100, lambda: self.main_paned.sashpos(0, sash_pos))
                    self.root.after(500, lambda: self.main_paned.sashpos(0, sash_pos))
                else:
                    # Force a fixed position at 250 pixels from the top (gives much more space to output area)
                    # The lower this number, the more space for the output area
                    target_pos = 250
                    
                    # Set immediately
                    self.main_paned.sashpos(0, target_pos)
                    
                    # And with delay to ensure it takes effect
                    self.root.after(100, lambda: self.main_paned.sashpos(0, target_pos))
                    self.root.after(500, lambda: self.main_paned.sashpos(0, target_pos))
                    
                    # Update the config so this position is saved
                    self.config['sash_position'] = target_pos
                    # Save the config immediately
                    self.save_window_config()
            except Exception:
                pass  # Silently ignore errors

    def load_window_config(self):
        """Load window configuration from file"""
        # Default values are already set in __init__, just need to add window position
        if 'window_x' not in self.config:
            self.config['window_x'] = None
        if 'window_y' not in self.config:
            self.config['window_y'] = None
        if 'active_tab' not in self.config:
            self.config['active_tab'] = 0
        
        try:
            # Try to use user's home directory for config file to avoid permission issues
            config_dir = os.path.join(os.path.expanduser("~"), ".p4wnforge")
            os.makedirs(config_dir, exist_ok=True)
            self.config_file = os.path.join(config_dir, "config.json")
            self.dictionaries_file = os.path.join(config_dir, "dictionaries.json")
            self.ssh_sessions_file = os.path.join(config_dir, "ssh_sessions.json")
            
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip():  # Check if file is not empty
                        saved_config = json.loads(content)
                        self.config.update(saved_config)
                        
                        # Apply dark mode setting if it exists in the config
                        if 'dark_mode' in self.config and hasattr(self, 'is_dark_mode'):
                            self.is_dark_mode.set(bool(self.config['dark_mode']))
        
            # Set window size and position
            self.root.geometry(f"{self.config['window_width']}x{self.config['window_height']}")
            if self.config['window_x'] is not None and self.config['window_y'] is not None:
                self.root.geometry(f"+{self.config['window_x']}+{self.config['window_y']}")
        except Exception as e:
            print(f"Error loading config: {e}")
            # Use default values from config
            self.root.geometry(f"{self.config['window_width']}x{self.config['window_height']}")

    def save_window_config(self):
        """Save window configuration to file"""
        try:
            # Ensure config file path is defined
            if not hasattr(self, 'config_file'):
                config_dir = os.path.join(os.path.expanduser("~"), ".p4wnforge")
                os.makedirs(config_dir, exist_ok=True)
                self.config_file = os.path.join(config_dir, "config.json")
            
            # Update config with current window state
            geometry = self.root.geometry().replace('x', '+').split('+')
            if len(geometry) >= 3:
                self.config['window_width'] = int(geometry[0])
                self.config['window_height'] = int(geometry[1])
                self.config['window_x'] = int(geometry[2])
                self.config['window_y'] = int(geometry[3]) if len(geometry) > 3 else 0
            
            # Capture the current sash position if main_paned exists
            if hasattr(self, 'main_paned'):
                try:
                    # Only save if sash position is reasonable (not collapsed)
                    current_sash_pos = self.main_paned.sashpos(0)
                    if current_sash_pos > 100:  # Ensure we're not saving a fully collapsed position
                        self.config['sash_position'] = current_sash_pos
                except Exception:
                    # If we can't get the sash position, just continue without updating it
                    pass
            
            # Save active tab
            if hasattr(self, 'tab_control'):
                self.config['active_tab'] = self.tab_control.index('current')
            
            # Save dark mode setting
            if hasattr(self, 'is_dark_mode'):
                self.config['dark_mode'] = self.is_dark_mode.get()
            
            # Make sure config directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # Write to file with proper encoding
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json_str = json.dumps(self.config, ensure_ascii=False, indent=2)
                f.write(json_str)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
            
        except Exception as e:
            print(f"Error saving config: {e}")
            import traceback
            traceback.print_exc()

    def _on_window_configure(self, event):
        """Handler for window resize and move events"""
        # Only handle events from the root window
        if event.widget == self.root:
            # Schedule a save after 500ms to avoid too many writes
            if hasattr(self, '_save_timer'):
                try:
                    self.root.after_cancel(self._save_timer)
                except Exception:
                    pass
            self._save_timer = self.root.after(500, self.save_window_config)

    def _on_sash_moved(self, event):
        """Handler for sash position change in the PanedWindow"""
        # Don't process events if the app is still initializing
        if not hasattr(self, 'main_paned'):
            return
        
        # Check if we have enough panes to have a sash
        try:
            panes = self.main_paned.panes()
            if len(panes) < 2:
                return  # Not enough panes to get sash position
        except Exception:
            return  # If we can't check panes, skip sash positioning
        
        # Get current sash position and store it in config
        try:
            sash_pos = self.main_paned.sashpos(0)
            if sash_pos > 0:  # Only update if we got a valid position
                # Only save if the position has actually changed
                if 'sash_position' not in self.config or self.config['sash_position'] != sash_pos:
                    self.config['sash_position'] = sash_pos
                    # Save configuration immediately after sash is moved
                    if hasattr(self, '_save_timer'):
                        try:
                            self.root.after_cancel(self._save_timer)
                        except Exception:
                            pass
                    self._save_timer = self.root.after(300, self.save_window_config)
        except Exception as e:
            # Silently ignore sash position errors
            pass

    def _on_window_close(self):
        """Handler for window close event"""
        # Capture the current sash position before closing
        try:
            if hasattr(self, 'main_paned'):
                current_sash_pos = self.main_paned.sashpos(0)
                if current_sash_pos > 0:  # Only save valid positions
                    self.config['sash_position'] = current_sash_pos
        except Exception:
            pass
            
        # Save configuration before closing
        self.save_window_config()
        # Save dictionaries before closing
        self.save_dictionaries()
        # Destroy the window
        self.root.destroy()

    def _on_dark_mode_changed(self, *args):
        """Handler for dark mode toggle"""
        # Update the theme
        self.update_theme()
        
        # Make sure dark mode setting is saved immediately
        self.config['dark_mode'] = self.is_dark_mode.get()
        self.save_window_config()
    
    def update_theme(self):
        is_dark = self.is_dark_mode.get()
        
        # Save the dark mode setting to config immediately
        self.config['dark_mode'] = is_dark
        
        if is_dark:
            # Dark theme
            self.style.theme_use('alt')  # Use alt theme as base for better compatibility
            self.style.configure('TFrame', background='#2E2E2E')
            self.style.configure('TLabel', background='#2E2E2E', foreground='#FFFFFF')
            self.style.configure('TNotebook', background='#2E2E2E', foreground='#FFFFFF')
            self.style.configure('TNotebook.Tab', background='#3E3E3E', foreground='#FFFFFF', padding=[10, 2])
            self.style.map('TNotebook.Tab', 
                          background=[('selected', '#5E5E5E'), ('active', '#4E4E4E')],
                          foreground=[('selected', '#FFFFFF'), ('active', '#FFFFFF')])
            
            # Improved button styling for dark mode with better hover contrast
            self.style.configure('TButton', background='#3E3E3E', foreground='#FFFFFF')
            self.style.map('TButton', 
                          background=[('active', '#4E4E4E'), ('pressed', '#2E2E2E')],
                          foreground=[('active', '#FFFFFF')])
            
            # Accent button style for prominent actions
            self.style.configure('Accent.TButton', background='#0078D7', foreground='#FFFFFF')
            self.style.map('Accent.TButton', 
                          background=[('active', '#1E88E5'), ('pressed', '#0063B1')],
                          foreground=[('active', '#FFFFFF')])
            
            # Improved checkbutton styling
            self.style.configure('TCheckbutton', 
                               background='#2E2E2E', 
                               foreground='#FFFFFF',
                               indicatorsize=14)
            self.style.map('TCheckbutton',
                         background=[('active', '#2E2E2E')],
                         foreground=[('active', '#FFFFFF')],
                         indicatorcolor=[('selected', '#4E9EFF'), ('', '#3E3E3E')])  # Blue when selected
            
            # Theme switch checkbutton - special styling for dark mode
            self.style.configure('Switch.TCheckbutton', 
                               background='#2E2E2E', 
                               foreground='#FFFFFF')
            self.style.map('Switch.TCheckbutton',
                         background=[('active', '#2E2E2E')],
                         foreground=[('active', '#FFFFFF')],
                         indicatorcolor=[('selected', '#4E9EFF'), ('', '#3E3E3E')],  # Blue when selected, dark gray when not
                         indicatorrelief=[('pressed', 'sunken')])
            
            # Improved Combobox styling for dark mode
            self.style.configure('TCombobox', 
                               background='#3E3E3E', 
                               foreground='#FFFFFF', 
                               fieldbackground='#3E3E3E', 
                               arrowcolor='#FFFFFF',
                               padding=(5, 1, 26, 1))  # Right padding ensures arrow is visible
            
            self.style.map('TCombobox', 
                         fieldbackground=[('readonly', '#3E3E3E')], 
                         foreground=[('readonly', '#FFFFFF')],
                         selectbackground=[('readonly', '#3E3E3E')])
            
            self.style.configure('TEntry', background='#3E3E3E', foreground='#FFFFFF', fieldbackground='#3E3E3E')
            self.style.configure('TLabelframe', background='#2E2E2E', foreground='#FFFFFF')
            self.style.configure('TLabelframe.Label', background='#2E2E2E', foreground='#FFFFFF')
            self.style.configure('TScrollbar', background='#3E3E3E', troughcolor='#2E2E2E', arrowcolor='#FFFFFF')
            self.style.map('TScrollbar', background=[('active', '#4E4E4E')])
            
            # Apply dark theme to all panes and labelframes
            self.style.configure('TPanedwindow', background='#2E2E2E')
            
            # Configure output text colors for dark mode
            if self.output_text:
                self.output_text.config(bg='#1E1E1E', fg='#CCCCCC', insertbackground='#FFFFFF')
            
            # Configure dictionary listbox for dark mode
            if hasattr(self, 'dict_listbox') and self.dict_listbox:
                self.dict_listbox.config(bg='#1E1E1E', fg='#CCCCCC', selectbackground='#4E4E4E', selectforeground='#FFFFFF')
            
            # Configure remote files listbox for dark mode
            if hasattr(self, 'remote_listbox') and self.remote_listbox:
                self.remote_listbox.config(bg='#1E1E1E', fg='#CCCCCC', selectbackground='#4E4E4E', selectforeground='#FFFFFF')
            
            # Configure SSH current directory entry for dark mode
            if hasattr(self, 'ssh_current_dir_entry') and self.ssh_current_dir_entry:
                self.ssh_current_dir_entry.config(readonlybackground='#3E3E3E', fg='#FFFFFF')
            
            # Set root background
            self.root.configure(bg='#2E2E2E')
            
        else:
            # Light theme
            self.style.theme_use('vista' if sys.platform == 'win32' else 'clam')  # Default theme
            self.style.configure('TFrame', background='#F0F0F0')
            self.style.configure('TLabel', background='#F0F0F0', foreground='#000000')
            self.style.configure('TNotebook', background='#F0F0F0', foreground='#000000')
            self.style.configure('TNotebook.Tab', background='#E0E0E0', foreground='#000000', padding=[10, 2])
            self.style.map('TNotebook.Tab', 
                          background=[('selected', '#FFFFFF'), ('active', '#F5F5F5')],
                          foreground=[('selected', '#000000'), ('active', '#000000')])
            
            # Button styling for light mode
            self.style.configure('TButton', background='#E0E0E0', foreground='#000000')
            self.style.map('TButton', 
                          background=[('active', '#D0D0D0'), ('pressed', '#C0C0C0')],
                          foreground=[('active', '#000000')])
            
            # Accent button style for prominent actions
            self.style.configure('Accent.TButton', background='#0078D7', foreground='#FFFFFF')
            self.style.map('Accent.TButton', 
                          background=[('active', '#1E88E5'), ('pressed', '#0063B1')],
                          foreground=[('active', '#FFFFFF')])
            
            self.style.configure('TCheckbutton', 
                               background='#F0F0F0', 
                               foreground='#000000',
                               indicatorsize=14)  # Larger indicator for better visibility
            self.style.map('TCheckbutton',
                          background=[('active', '#F0F0F0')],
                          foreground=[('active', '#000000')],
                          indicatorcolor=[('selected', '#0078D7'), ('', '#E0E0E0')])
            
            # Theme switch checkbutton - special styling for light mode
            self.style.configure('Switch.TCheckbutton', 
                               background='#F0F0F0', 
                               foreground='#000000')
            self.style.map('Switch.TCheckbutton',
                         background=[('active', '#F0F0F0')],
                         foreground=[('active', '#000000')],
                         indicatorcolor=[('selected', '#0078D7'), ('', '#E0E0E0')],  # Blue when selected, light gray when not
                         indicatorrelief=[('pressed', 'sunken')])
            
            # Improved Combobox styling for light mode
            self.style.configure('TCombobox', 
                               background='#FFFFFF', 
                               foreground='#000000', 
                               fieldbackground='#FFFFFF', 
                               arrowcolor='#000000',
                               padding=(5, 1, 26, 1))  # Right padding ensures arrow is visible
            
            self.style.map('TCombobox', 
                         fieldbackground=[('readonly', '#FFFFFF')], 
                         foreground=[('readonly', '#000000')],
                         selectbackground=[('readonly', '#FFFFFF')])
            
            self.style.configure('TEntry', background='#FFFFFF', foreground='#000000', fieldbackground='#FFFFFF')
            self.style.configure('TLabelframe', background='#F0F0F0', foreground='#000000')
            self.style.configure('TLabelframe.Label', background='#F0F0F0', foreground='#000000')
            self.style.configure('TScrollbar', background='#E0E0E0', troughcolor='#F0F0F0', arrowcolor='#000000')
            self.style.map('TScrollbar', background=[('active', '#D0D0D0')])
            
            # Apply light theme to all panes
            self.style.configure('TPanedwindow', background='#F0F0F0')
            
            # Configure output text colors for light mode
            if self.output_text:
                self.output_text.config(bg='#FFFFFF', fg='#000000', insertbackground='#000000')
            
            # Configure dictionary listbox for light mode
            if hasattr(self, 'dict_listbox') and self.dict_listbox:
                self.dict_listbox.config(bg='#FFFFFF', fg='#000000', selectbackground='#0078D7', selectforeground='#FFFFFF')
            
            # Configure remote files listbox for light mode
            if hasattr(self, 'remote_listbox') and self.remote_listbox:
                self.remote_listbox.config(bg='#FFFFFF', fg='#000000', selectbackground='#0078D7', selectforeground='#FFFFFF')
            
            # Configure SSH current directory entry for light mode
            if hasattr(self, 'ssh_current_dir_entry') and self.ssh_current_dir_entry:
                self.ssh_current_dir_entry.config(readonlybackground='#F0F0F0', fg='#000000')
            
            # Set root background
            self.root.configure(bg='#F0F0F0')
        
        # Fix combobox dropdowns for current theme
        self._fix_combobox_display()
        
        # Update all existing widgets with the new theme
        self._update_widget_theme(self.root)
        
        # Make sure the dark mode checkbox reflects the correct state
        if hasattr(self, 'dark_mode_cb'):
            if is_dark:
                self.dark_mode_cb.state(['selected'])
            else:
                self.dark_mode_cb.state(['!selected'])
        
        # Save settings immediately to ensure they persist
        self.save_window_config()
    
    def _update_widget_theme(self, parent):
        """Recursively update all widgets with the current theme"""
        # Process all children
        try:
            for child in parent.winfo_children():
                # Update based on widget type
                widget_class = child.winfo_class()
                
                # Apply specific styling based on widget type
                if widget_class == 'TLabelframe':
                    bg_color = '#2E2E2E' if self.is_dark_mode.get() else '#F0F0F0'
                    fg_color = '#FFFFFF' if self.is_dark_mode.get() else '#000000'
                    child.configure(style='TLabelframe')
                    
                    # Process LabelFrame label
                    for sub_child in child.winfo_children():
                        if sub_child.winfo_class() == 'TLabel':
                            sub_child.configure(style='TLabelframe.Label')
                
                elif widget_class == 'TButton':
                    child.configure(style='TButton')
                
                elif widget_class == 'TCombobox':
                    # Apply correct style to combobox
                    if not isinstance(child, FixedCombobox):
                        fg_color = '#FFFFFF' if self.is_dark_mode.get() else '#000000'
                        child.configure(style='TCombobox', foreground=fg_color)
                
                elif widget_class == 'TCheckbutton':
                    child.configure(style='TCheckbutton')
                
                elif widget_class == 'TEntry':
                    child.configure(style='TEntry')
                
                elif widget_class == 'TScrollbar':
                    child.configure(style='TScrollbar')
                
                # Recursively process all children
                self._update_widget_theme(child)
        except Exception as e:
            print(f"Error in _update_widget_theme: {e}")
    
    def _fix_combobox_display(self):
        """Fix combobox display issues after theme change"""
        is_dark = self.is_dark_mode.get()
        # Configure all tk optiondb settings for comboboxes
        if is_dark:
            self.root.tk.eval("""
                option add *TCombobox*Listbox.background #3E3E3E
                option add *TCombobox*Listbox.foreground #FFFFFF
                option add *TCombobox*Listbox.selectBackground #4E4E4E
                option add *TCombobox*Listbox.selectForeground #FFFFFF
            """)
        else:
            self.root.tk.eval("""
                option add *TCombobox*Listbox.background white
                option add *TCombobox*Listbox.foreground black
                option add *TCombobox*Listbox.selectBackground #0078D7
                option add *TCombobox*Listbox.selectForeground white
            """)
    
    def _update_all_comboboxes(self, is_dark):
        """Update all FixedCombobox instances to reflect the current theme"""
        # Update attack type combobox
        if hasattr(self, 'office_attack_type') and isinstance(self.office_attack_type, FixedCombobox):
            if is_dark:
                self.office_attack_type.configure(foreground='white')
            else:
                self.office_attack_type.configure(foreground='black')
        
        # Update other comboboxes
        for tab in [self.office_tab, self.pdf_tab, self.hash_tab, self.dictionary_tab]:
            if tab:
                for child in tab.winfo_children():
                    if isinstance(child, ttk.LabelFrame):
                        for grandchild in child.winfo_children():
                            try:
                                if isinstance(grandchild, FixedCombobox):
                                    grandchild.update_theme(is_dark)
                            except Exception:
                                pass  # Skip widgets that can't be configured
    
    def setup_office_tab(self):
        frame = ttk.LabelFrame(self.office_tab, text="Microsoft Office Document Cracking", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(frame, text="Office Document:").grid(column=0, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.target_file_path, width=50).grid(column=1, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Button(frame, text="Browse", command=lambda: self.browse_file([("Word Documents", "*.docx *.doc"),
                                                                         ("Excel Documents", "*.xlsx *.xls"),
                                                                         ("All Files", "*.*")])).grid(column=2, row=0, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(frame, text="Office Version:").grid(column=0, row=1, sticky=tk.W, padx=5, pady=5)
        office_version = FixedCombobox(frame, is_dark_mode_var=self.is_dark_mode, values=["Office 2007", "Office 2010", "Office 2013", "Office 2016", "Office 2019", "Office 365"])
        office_version.grid(column=1, row=1, sticky=tk.W, padx=5, pady=5)
        office_version.current(5)  # Default to Office 365
        
        # Add attack type option
        ttk.Label(frame, text="Attack Type:").grid(column=0, row=2, sticky=tk.W, padx=5, pady=3)
        self.office_attack_type = FixedCombobox(frame, is_dark_mode_var=self.is_dark_mode, values=[
            "Dictionary Attack",
            "Bruteforce"
        ])
        self.office_attack_type.grid(column=1, row=2, sticky=tk.W, padx=5, pady=3)
        self.office_attack_type.current(0)  # Default to Dictionary Attack
        self.office_attack_type.bind("<<ComboboxSelected>>", self._on_office_attack_type_changed)
        
        self.office_crack_button = ttk.Button(frame, text="Start Cracking", command=lambda: self.toggle_cracking("office"))
        self.office_crack_button.grid(column=1, row=3, sticky=tk.E, padx=5, pady=20)
    
    def setup_pdf_tab(self):
        frame = ttk.LabelFrame(self.pdf_tab, text="PDF Document Cracking", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(frame, text="PDF Document:").grid(column=0, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.target_file_path, width=50).grid(column=1, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Button(frame, text="Browse", command=lambda: self.browse_file([("PDF Files", "*.pdf"), ("All Files", "*.*")])).grid(column=2, row=0, sticky=tk.W, padx=5, pady=5)
        
        # Add attack type option
        ttk.Label(frame, text="Attack Type:").grid(column=0, row=1, sticky=tk.W, padx=5, pady=3)
        self.pdf_attack_type = FixedCombobox(frame, is_dark_mode_var=self.is_dark_mode, values=[
            "Dictionary Attack",
            "Bruteforce"
        ])
        self.pdf_attack_type.grid(column=1, row=1, sticky=tk.W, padx=5, pady=3)
        self.pdf_attack_type.current(0)  # Default to Dictionary Attack
        
        # PDF version selection remains for interface consistency
        ttk.Label(frame, text="PDF Version:").grid(column=0, row=2, sticky=tk.W, padx=5, pady=5)
        self.pdf_version_combobox = FixedCombobox(frame, is_dark_mode_var=self.is_dark_mode, values=[
            "Acrobat 5.0 and later (PDF 1.4)",
            "Acrobat 6.0 and later (PDF 1.5)",
            "Acrobat 7.0 and later (PDF 1.6)",
            "Acrobat 9.0 and later (PDF 1.7)"
        ])
        self.pdf_version_combobox.grid(column=1, row=2, sticky=tk.W, padx=5, pady=5)
        self.pdf_version_combobox.current(3)
        
        # Custom function for PDF toggle that prevents options dialog during active cracking
        def pdf_toggle_cracking():
            if self.is_cracking:
                # If already cracking, just stop without showing options
                self.stop_cracking()
            else:
                # Otherwise start cracking as normal
                self.toggle_cracking("pdf")
        
        self.pdf_crack_button = ttk.Button(frame, text="Start Cracking", command=pdf_toggle_cracking)
        self.pdf_crack_button.grid(column=1, row=3, sticky=tk.E, padx=5, pady=20)
    
    def setup_hash_tab(self):
        frame = ttk.LabelFrame(self.hash_tab, text="NTLM Hash Cracking", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(frame, text="Hash File:").grid(column=0, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.target_file_path, width=50).grid(column=1, row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Button(frame, text="Browse", command=lambda: self.browse_file([("Hash Files", "*.hash *.hashes"), ("Text Files", "*.txt"), ("All Files", "*.*")])).grid(column=2, row=0, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(frame, text="Hash Type:").grid(column=0, row=1, sticky=tk.W, padx=5, pady=5)
        self.hash_type_combo = FixedCombobox(frame, is_dark_mode_var=self.is_dark_mode, values=["NTLMv2", "NTLM", "NetNTLMv2", "NetNTLM"])
        self.hash_type_combo.grid(column=1, row=1, sticky=tk.W, padx=5, pady=5)
        self.hash_type_combo.current(2)  # Select NetNTLMv2 by default (index 2)
        
        # Add attack type option
        ttk.Label(frame, text="Attack Type:").grid(column=0, row=2, sticky=tk.W, padx=5, pady=3)
        self.hash_attack_type = FixedCombobox(frame, is_dark_mode_var=self.is_dark_mode, values=[
            "Dictionary Attack",
            "Bruteforce"
        ])
        self.hash_attack_type.grid(column=1, row=2, sticky=tk.W, padx=5, pady=3)
        self.hash_attack_type.current(0)  # Default to Dictionary Attack
        
        self.hash_crack_button = ttk.Button(frame, text="Start Cracking", command=lambda: self.toggle_cracking("hash"))
        self.hash_crack_button.grid(column=1, row=3, sticky=tk.E, padx=5, pady=20)
    
    def setup_about_tab(self):
        """Set up the About tab with logo and developer information"""
        frame = ttk.Frame(self.about_tab, padding="20")
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Logo display
        logo_frame = ttk.Frame(frame)
        logo_frame.pack(fill=tk.X, pady=10)
        
        # Create a placeholder logo label
        logo_label = ttk.Label(logo_frame, text="P4wnForge")
        logo_label.pack(anchor=tk.CENTER)
        
        try:
            # Try to load the logo image
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "P4wnForge.webp")
            if os.path.exists(logo_path):
                try:
                    img = Image.open(logo_path)
                    # Resize image if needed
                    img = img.resize((200, 200), Image.LANCZOS)
                    logo_img = ImageTk.PhotoImage(img)
                    logo_label.config(image=logo_img, text="")
                    logo_label.image = logo_img  # Keep a reference to prevent garbage collection
                except Exception as e:
                    print(f"Error processing logo image: {e}")
        except Exception as e:
            print(f"Error in logo setup: {e}")
        
        # About information
        info_frame = ttk.Frame(frame)
        info_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        ttk.Label(info_frame, text="Advanced Password Recovery Tool", font=("Helvetica", 12)).pack(anchor=tk.CENTER)
        ttk.Label(info_frame, text="Version 1.5.0").pack(anchor=tk.CENTER, pady=10)
        
        # Developer info
        ttk.Label(info_frame, text="Developed by: Detective Aaron Cuddeback", font=("Helvetica", 10, "bold")).pack(anchor=tk.CENTER, pady=5)
        ttk.Label(info_frame, text="Email: cuddebaa@edso.org").pack(anchor=tk.CENTER)
        
        # LinkedIn link
        linkedin_link = ttk.Label(info_frame, text="LinkedIn", foreground="blue", cursor="hand2")
        linkedin_link.pack(anchor=tk.CENTER, pady=2)
        linkedin_link.bind("<Button-1>", lambda e: webbrowser.open("https://linkedin.com/in/aaroncu"))
        
        # Add hightech.png logo 
        try:
            hightech_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hightech.png")
            if os.path.exists(hightech_path):
                hightech_img = Image.open(hightech_path)
                # Resize image for appropriate display
                hightech_img = hightech_img.resize((94, 94), Image.LANCZOS)
                hightech_photo = ImageTk.PhotoImage(hightech_img)
                hightech_label = ttk.Label(info_frame, image=hightech_photo)
                hightech_label.image = hightech_photo  # Keep a reference to prevent garbage collection
                hightech_label.pack(anchor=tk.CENTER, pady=10)
        except Exception as e:
            print(f"Error adding hightech logo: {e}")
        
        ttk.Label(info_frame, text="© 2023-2025 All Rights Reserved").pack(anchor=tk.CENTER, pady=10)
        
        # Legal disclaimer
        disclaimer_frame = ttk.LabelFrame(frame, text="Legal Disclaimer")
        disclaimer_frame.pack(fill=tk.X, expand=False, pady=10)
        
        disclaimer_text = ("This tool is provided for educational and professional security testing purposes only. "
                           "Use responsibly and only on systems you own or have explicit permission to test. "
                           "Unauthorized password cracking attempts may be illegal.")
        
        disclaimer_label = ttk.Label(disclaimer_frame, text=disclaimer_text, wraplength=500, justify=tk.LEFT)
        disclaimer_label.pack(padx=10, pady=10)
    
    def setup_dictionary_tab(self):
        """Set up the Dictionary Manager tab for managing wordlists"""
        frame = ttk.LabelFrame(self.dictionary_tab, text="Dictionary File Manager", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Show the current dictionary directory
        dict_dir = self._get_dictionary_directory()
        dict_path_frame = ttk.Frame(frame)
        dict_path_frame.pack(fill=tk.X, expand=False, pady=5)
        ttk.Label(dict_path_frame, text="Dictionary Location:").pack(side=tk.LEFT, padx=5)
        ttk.Label(dict_path_frame, text=dict_dir).pack(side=tk.LEFT, padx=5)
        
        # Dictionary list with scrollbar
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.dict_listbox = tk.Listbox(list_frame, height=10, width=60, yscrollcommand=scrollbar.set)
        self.dict_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.dict_listbox.yview)
        
        # Set initial colors based on theme
        if self.is_dark_mode.get():
            self.dict_listbox.config(bg='#1E1E1E', fg='#CCCCCC', selectbackground='#4E4E4E', selectforeground='#FFFFFF')
        else:
            self.dict_listbox.config(bg='#FFFFFF', fg='#000000', selectbackground='#0078D7', selectforeground='#FFFFFF')
        
        # Load available dictionary list into the UI
        self.load_dictionary_list()
        
        # Button frame
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        add_button = ttk.Button(button_frame, text="Add Dictionary", command=self.add_dictionary)
        add_button.pack(side=tk.LEFT, padx=5)
        
        remove_button = ttk.Button(button_frame, text="Remove Selected", command=self.remove_dictionary)
        remove_button.pack(side=tk.LEFT, padx=5)
        
        use_button = ttk.Button(button_frame, text="Use Selected", command=self.use_dictionary)
        use_button.pack(side=tk.LEFT, padx=5)
        
        # Dictionary testing
        test_frame = ttk.LabelFrame(frame, text="Dictionary Statistics")
        test_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(test_frame, text="Selected dictionary contains:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.dict_stats_label = ttk.Label(test_frame, text="No dictionary selected")
        self.dict_stats_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        analyze_button = ttk.Button(test_frame, text="Analyze", command=self.analyze_dictionary)
        analyze_button.grid(row=0, column=2, padx=5, pady=5)
        
        # Dictionary download section
        download_frame = ttk.LabelFrame(frame, text="Download Common Dictionaries")
        download_frame.pack(fill=tk.X, pady=10)
        
        common_dicts = [
            "rockyou.txt (14.3 MB) - Most common passwords",
            "10-million-password-list-top-1000000.txt (7.5 MB) - Common passwords",
            "english-words.txt (4.2 MB) - English dictionary"
        ]
        
        self.download_combo = FixedCombobox(download_frame, is_dark_mode_var=self.is_dark_mode, values=common_dicts, width=50)
        self.download_combo.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.download_combo.current(0)
        
        download_button = ttk.Button(download_frame, text="Download", command=self.download_dictionary)
        download_button.grid(row=0, column=1, padx=5, pady=5)
        
        # Download progress bar (initially hidden)
        progress_frame = ttk.Frame(download_frame)
        progress_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        
        self.download_status_label = ttk.Label(progress_frame, text="")
        self.download_status_label.pack(anchor=tk.W, pady=(5, 0))
        
        self.download_progressbar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=400, mode='determinate')
        self.download_progressbar.pack(fill=tk.X, pady=5)
        
        # Hide progress bar initially
        self.download_progressbar.pack_forget()
        self.download_status_label.pack_forget()
    
    def load_dictionary_list(self):
        """Load the list of dictionaries and scan default locations"""
        # First, ensure the dictionaries file is defined
        if not hasattr(self, 'dictionaries_file'):
            config_dir = os.path.join(os.path.expanduser("~"), ".p4wnforge")
            os.makedirs(config_dir, exist_ok=True)
            self.dictionaries_file = os.path.join(config_dir, "dictionaries.json")
        
        # Load saved dictionaries
        self.load_saved_dictionaries()
        
        # Find default dictionaries if the list is empty
        if not self.dictionary_files:
            self.find_default_dictionaries()
            
        # Update the listbox
        if hasattr(self, 'dict_listbox'):
            self.dict_listbox.delete(0, tk.END)
            for dict_path in self.dictionary_files:
                self.dict_listbox.insert(tk.END, dict_path)

    def load_saved_dictionaries(self):
        """Load the list of saved dictionaries from file"""
        try:
            # Ensure the dictionaries file is defined
            if not hasattr(self, 'dictionaries_file'):
                config_dir = os.path.join(os.path.expanduser("~"), ".p4wnforge")
                os.makedirs(config_dir, exist_ok=True)
                self.dictionaries_file = os.path.join(config_dir, "dictionaries.json")
                
            if os.path.exists(self.dictionaries_file):
                with open(self.dictionaries_file, 'r') as f:
                    saved_dicts = json.load(f)
                    self.dictionary_files = saved_dicts
            else:
                self.dictionary_files = []
        except Exception as e:
            print(f"Error loading dictionaries: {e}")
            self.dictionary_files = []

    def save_dictionaries(self):
        """Save the current list of dictionaries to file"""
        try:
            # Ensure the dictionaries file is defined
            if not hasattr(self, 'dictionaries_file'):
                config_dir = os.path.join(os.path.expanduser("~"), ".p4wnforge")
                os.makedirs(config_dir, exist_ok=True)
                self.dictionaries_file = os.path.join(config_dir, "dictionaries.json")
                
            # Filter out dictionaries that no longer exist
            self.dictionary_files = [d for d in self.dictionary_files if os.path.exists(d)]
            
            # Save to file
            with open(self.dictionaries_file, 'w') as f:
                json.dump(self.dictionary_files, f)
        except Exception as e:
            print(f"Error saving dictionaries: {e}")

    def add_dictionary(self):
        """Add a dictionary file to the list"""
        # First determine the dictionary storage directory (same as download location)
        dict_dir = self._get_dictionary_directory()
        if not dict_dir:
            messagebox.showerror("Error", "Could not find a writable directory for dictionaries")
            return
        
        # Create the directory if it doesn't exist
        os.makedirs(dict_dir, exist_ok=True)
        
        # Open file dialog to select dictionary files
        filepaths = filedialog.askopenfilenames(
            title="Select Dictionary Files",
            initialdir=dict_dir,
            filetypes=[("Text Files", "*.txt"), ("Dictionary Files", "*.dict"), ("All Files", "*.*")]
        )
        
        if filepaths:
            added_count = 0
            for filepath in filepaths:
                # Generate destination path
                filename = os.path.basename(filepath)
                dest_path = os.path.join(dict_dir, filename)
                
                # Check if already exists in our dictionaries folder
                if os.path.exists(dest_path) and os.path.samefile(filepath, dest_path):
                    # File is already in our dictionary folder, just add to list if not already there
                    if dest_path not in self.dictionary_files:
                        self.dict_listbox.insert(tk.END, dest_path)
                        self.dictionary_files.append(dest_path)
                        self.log_output(f"Added dictionary: {dest_path}")
                        added_count += 1
                    else:
                        self.log_output(f"Dictionary already exists: {dest_path}")
                else:
                    # Need to copy the file to our dictionaries location
                    try:
                        # If destination file already exists with a different file,
                        # create a unique filename
                        if os.path.exists(dest_path):
                            base, ext = os.path.splitext(filename)
                            dest_path = os.path.join(dict_dir, f"{base}_{int(time.time())}{ext}")
                            
                        # Copy the file
                        self.log_output(f"Copying {filepath} to {dict_dir}...")
                        shutil.copy2(filepath, dest_path)
                        
                        # Add to list
                        if dest_path not in self.dictionary_files:
                            self.dict_listbox.insert(tk.END, dest_path)
                            self.dictionary_files.append(dest_path)
                            self.log_output(f"Added dictionary: {dest_path}")
                            added_count += 1
                    except Exception as e:
                        self.log_output(f"Error copying dictionary: {str(e)}")
                        messagebox.showerror("Error", f"Could not copy file: {str(e)}")
            
            # Save the updated dictionary list
            if added_count > 0:
                self.save_dictionaries()
                messagebox.showinfo("Success", f"Added {added_count} dictionaries to {dict_dir}")
                
        # If no files were selected, show message
        elif len(filepaths) == 0:
            self.log_output("No dictionary files were selected.")

    def _get_dictionary_directory(self):
        """Get a writable directory for dictionaries storage"""
        try:
            # First try to use the app's root directory
            app_dir = os.path.dirname(os.path.abspath(__file__))
            dict_dir = os.path.join(app_dir, "dictionaries")
            os.makedirs(dict_dir, exist_ok=True)
            
            # Check if we have write permission
            if os.access(dict_dir, os.W_OK):
                return dict_dir
                
            # If app directory isn't writable, fallback to user's home directory
            self.log_output("Warning: Cannot write to app directory, using fallback location")
            dict_dir = os.path.join(os.path.expanduser("~"), ".p4wnforge", "dictionaries")
            os.makedirs(dict_dir, exist_ok=True)
            
            if os.access(dict_dir, os.W_OK):
                return dict_dir
                
            # Try Documents folder if home directory isn't writable
            documents_dir = os.path.join(os.path.expanduser("~"), "Documents")
            dict_dir = os.path.join(documents_dir, "P4wnForge_Dictionaries")
            os.makedirs(dict_dir, exist_ok=True)
            
            if os.access(dict_dir, os.W_OK):
                return dict_dir
                
            # Try Temp directory as final fallback
            dict_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "P4wnForge_Dictionaries")
            os.makedirs(dict_dir, exist_ok=True)
            
            if os.access(dict_dir, os.W_OK):
                return dict_dir
                
        except Exception as e:
            self.log_output(f"Error finding dictionary directory: {str(e)}")
            
        # Final fallback to current directory
        try:
            dict_dir = os.path.join(os.getcwd(), "dictionaries")
            os.makedirs(dict_dir, exist_ok=True)
            return dict_dir if os.access(dict_dir, os.W_OK) else None
        except Exception:
            return None

    def remove_dictionary(self):
        """Remove selected dictionary from the list"""
        selected = self.dict_listbox.curselection()
        if selected:
            for index in selected[::-1]:  # Reverse to avoid index shifting
                dict_path = self.dict_listbox.get(index)
                self.dict_listbox.delete(index)
                if dict_path in self.dictionary_files:
                    self.dictionary_files.remove(dict_path)
                    self.log_output(f"Removed dictionary: {dict_path}")
            
            # Save the updated dictionary list
            self.save_dictionaries()

    def use_dictionary(self):
        """Use selected dictionary for password cracking"""
        selected = self.dict_listbox.curselection()
        if selected:
            dict_path = self.dict_listbox.get(selected[0])
            self.password_list_path.set(dict_path)
            self.log_output(f"Selected dictionary: {dict_path}")
        else:
            messagebox.showinfo("Selection Required", "Please select a dictionary from the list")

    def analyze_dictionary(self):
        """Analyze the selected dictionary file and show statistics"""
        selected = self.dict_listbox.curselection()
        if not selected:
            messagebox.showinfo("Selection Required", "Please select a dictionary from the list")
            return
        
        dict_path = self.dict_listbox.get(selected[0])
        try:
            stats = {"total_lines": 0, "min_length": float('inf'), "max_length": 0, "avg_length": 0}
            total_length = 0
            
            with open(dict_path, 'r', encoding='latin-1', errors='ignore') as f:
                for line in f:
                    password = line.strip()
                    if password:
                        stats["total_lines"] += 1
                        pw_len = len(password)
                        stats["min_length"] = min(stats["min_length"], pw_len)
                        stats["max_length"] = max(stats["max_length"], pw_len)
                        total_length += pw_len
            
            if stats["total_lines"] > 0:
                stats["avg_length"] = round(total_length / stats["total_lines"], 2)
                
                # Get file size
                file_size = os.path.getsize(dict_path)
                if file_size < 1024:
                    size_str = f"{file_size} bytes"
                elif file_size < 1024 * 1024:
                    size_str = f"{file_size/1024:.2f} KB"
                else:
                    size_str = f"{file_size/(1024*1024):.2f} MB"
                
                stats_text = f"{stats['total_lines']} passwords, {size_str}\n"
                stats_text += f"Length: min={stats['min_length']}, max={stats['max_length']}, avg={stats['avg_length']}"
                
                self.dict_stats_label.config(text=stats_text)
                self.log_output(f"Dictionary analysis for {os.path.basename(dict_path)}: {stats_text}")
            else:
                self.dict_stats_label.config(text="Dictionary is empty")
                self.log_output(f"Dictionary {os.path.basename(dict_path)} is empty")
                
        except Exception as e:
            self.dict_stats_label.config(text=f"Error analyzing dictionary")
            self.log_output(f"Error analyzing dictionary: {str(e)}")

    def download_dictionary(self):
        """Download a common dictionary file"""
        selected = self.download_combo.get()
        
        # Dictionary download URLs
        download_info = {
            "rockyou.txt (14.3 MB) - Most common passwords": {
                "url": "https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt",
                "filename": "rockyou.txt",
                "size_mb": 14.3
            },
            "10-million-password-list-top-1000000.txt (7.5 MB) - Common passwords": {
                "url": "https://github.com/danielmiessler/SecLists/raw/master/Passwords/Common-Credentials/10-million-password-list-top-1000000.txt",
                "filename": "10-million-password-list-top-1000000.txt",
                "size_mb": 7.5
            },
            "english-words.txt (4.2 MB) - English dictionary": {
                "url": "https://raw.githubusercontent.com/dwyl/english-words/master/words.txt",
                "filename": "english-words.txt",
                "size_mb": 4.2
            }
        }
        
        if selected in download_info:
            info = download_info[selected]
            
            # Ensure we use the app's dictionary directory
            app_dir = os.path.dirname(os.path.abspath(__file__))
            dict_dir = os.path.join(app_dir, "dictionaries")
            
            try:
                os.makedirs(dict_dir, exist_ok=True)
                
                # Check if we have write permission
                if not os.access(dict_dir, os.W_OK):
                    # Fall back to the user's directory
                    self.log_output("Warning: Cannot write to app directory, falling back to alternate location")
                    dict_dir = self._get_dictionary_directory()
                    if not dict_dir:
                        messagebox.showerror("Error", "Could not find a writable directory for dictionaries")
                        return
            except Exception as e:
                self.log_output(f"Error creating dictionary directory: {str(e)}")
                dict_dir = self._get_dictionary_directory()
                if not dict_dir:
                    messagebox.showerror("Error", "Could not find a writable directory for dictionaries")
                    return
            
            output_path = os.path.join(dict_dir, info["filename"])
            
            # Check if the file already exists
            if os.path.exists(output_path):
                # Ask user if they want to redownload
                if not messagebox.askyesno(
                    "File Exists", 
                    f"The dictionary '{info['filename']}' already exists in {dict_dir}.\n\nDo you want to download it again and replace the existing file?"
                ):
                    self.log_output(f"Download cancelled - '{info['filename']}' already exists")
                    
                    # Check if the dictionary is already in our list
                    if output_path not in self.dictionary_files:
                        self.dictionary_files.append(output_path)
                        self.dict_listbox.insert(tk.END, output_path)
                        self.save_dictionaries()
                        self.log_output(f"Added existing dictionary to list: {output_path}")
                    
                    return
                else:
                    self.log_output(f"Redownloading '{info['filename']}' and replacing existing file")
            
            # Show progress bar
            self.download_status_label.config(text=f"Downloading {info['filename']} to {dict_dir}...")
            self.download_status_label.pack(anchor=tk.W, pady=(5, 0))
            self.download_progressbar.pack(fill=tk.X, pady=5)
            self.download_progressbar["value"] = 0
            
            # Log download start
            self.log_output(f"Downloading {info['filename']} to {dict_dir}...")
            
            # Start download in a separate thread
            thread = threading.Thread(target=self._download_file_with_progress, 
                                      args=(info["url"], output_path, info["size_mb"]))
            thread.daemon = True
            thread.start()
        else:
            messagebox.showinfo("Selection Required", "Please select a dictionary to download")

    def _download_file_with_progress(self, url, output_path, total_size_mb):
        """Download a file from URL to the given path with progress updates"""
        try:
            # First check if we have write permission to the output directory
            output_dir = os.path.dirname(output_path)
            if not os.access(output_dir, os.W_OK):
                error_msg = f"Permission denied: Cannot write to {output_dir}"
                self.log_output(f"Download failed: {error_msg}")
                self.root.after(0, lambda: self._update_progress(0, f"Download failed: {error_msg}"))
                self.root.after(2000, self._hide_progress)
                return
                
            # Try to open the output file for writing (to test permissions)
            try:
                with open(output_path, 'wb') as test_file:
                    pass  # Just testing if we can write
            except PermissionError:
                error_msg = f"Permission denied: Cannot write to {output_path}"
                self.log_output(f"Download failed: {error_msg}")
                self.root.after(0, lambda: self._update_progress(0, f"Download failed: {error_msg}"))
                self.root.after(2000, self._hide_progress)
                return
            except Exception as e:
                # Other file access errors
                self.log_output(f"Download failed: {str(e)}")
                self.root.after(0, lambda: self._update_progress(0, f"Download failed: {str(e)}"))
                self.root.after(2000, self._hide_progress)
                return
                
            # Begin download
            try:
                with requests.get(url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    total_size = int(r.headers.get('content-length', 0))
                    
                    if total_size == 0:
                        # If content-length is not provided, use the estimate from our info
                        total_size = total_size_mb * 1024 * 1024
                    
                    downloaded = 0
                    
                    with open(output_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                # Update progress every 50KB
                                if downloaded % (50 * 1024) < 8192:
                                    progress = (downloaded / total_size) * 100 if total_size > 0 else 0
                                    progress_mb = downloaded / (1024 * 1024)
                                    total_mb = total_size / (1024 * 1024)
                                    
                                    # Update progress bar in the main thread
                                    self.root.after(0, lambda: self._update_progress(
                                        progress, 
                                        f"Downloading: {progress:.1f}% ({progress_mb:.1f}MB / {total_mb:.1f}MB)"
                                    ))
                                    
                                    # Also log to output window occasionally
                                    if downloaded % (1024 * 1024) < 8192:  # Every ~1MB
                                        self.log_output(f"Downloading: {progress:.1f}% ({progress_mb:.1f}MB / {total_mb:.1f}MB)")
            except requests.exceptions.RequestException as e:
                self.root.after(0, lambda: self._update_progress(0, f"Download failed: Network error: {str(e)}"))
                self.root.after(2000, self._hide_progress)
                self.log_output(f"Download failed: Network error: {str(e)}")
                return
            
            # Download completed
            self.root.after(0, lambda: self._update_progress(
                100, f"Download completed: {os.path.basename(output_path)}"
            ))
            
            # Add to dictionary list in the main thread
            if output_path not in self.dictionary_files:
                self.dictionary_files.append(output_path)
                self.root.after(0, lambda: self.dict_listbox.insert(tk.END, output_path))
                # Save the updated dictionary list
                self.root.after(100, self.save_dictionaries)
            
            # Hide progress bar after 2 seconds
            self.root.after(2000, self._hide_progress)
            
            # Log completion to output window
            self.log_output(f"Download completed: {output_path}")
            
            # Show a success message
            filename = os.path.basename(output_path)
            dict_dir = os.path.dirname(output_path)
            self.root.after(0, lambda: messagebox.showinfo("Download Complete", 
                                                          f"Dictionary '{filename}' has been downloaded to:\n{dict_dir}"))
        
        except Exception as e:
            # Update UI in main thread
            self.root.after(0, lambda: self._update_progress(0, f"Download failed: {str(e)}"))
            self.root.after(2000, self._hide_progress)
            
            # Log error to output window
            self.log_output(f"Download failed: {str(e)}")

    def _update_progress(self, value, status_text):
        """Update the progress bar and status label from the main thread"""
        self.download_progressbar["value"] = value
        self.download_status_label.config(text=status_text)
        
    def _hide_progress(self):
        """Hide the progress bar and reset status"""
        self.download_progressbar.pack_forget()
        self.download_status_label.pack_forget()

    def browse_password_list(self):
        """Open file dialog to browse for password list"""
        # Get the dictionaries directory path
        dict_dir = self._get_dictionary_directory()
        if not dict_dir:
            # Default to current directory if we can't get a dictionary directory
            dict_dir = os.getcwd()
        
        filename = filedialog.askopenfilename(
            title="Select Password List",
            initialdir=dict_dir,
            filetypes=[("Text Files", "*.txt"), ("Word Lists", "*.dict"), ("All Files", "*.*")]
        )
        if filename:
            self.password_list_path.set(filename)
    
    def browse_file(self, filetypes):
        # Get current tab to determine initial directory
        current_tab = self.tab_control.tab(self.tab_control.select(), "text").lower()
        
        # Set initial directory based on current tab
        if current_tab == "ntlm hash":
            # For NTLM hash tab, default to the hashes/ntlm directory
            hashes_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hashes")
            ntlm_dir = os.path.join(hashes_dir, "ntlm")
            # Create the directory if it doesn't exist
            os.makedirs(ntlm_dir, exist_ok=True)
            initial_dir = ntlm_dir
        else:
            # For other tabs, no specific initial directory
            initial_dir = None
        
        filename = filedialog.askopenfilename(
            title="Select Target File",
            initialdir=initial_dir,
            filetypes=filetypes
        )
        if filename:
            self.target_file_path.set(filename)
            self.current_tab = current_tab
    
    def find_extraction_tool(self, tool_name):
        """Search for extraction tools (office2john.py or pdfbrute.py) in common locations."""
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
        self.log_output("Checking for extraction tools...")
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
        pdfbrute_found = False
        
        for path in search_paths:
            if not path:
                continue
            office2john_path = os.path.join(path, "office2john.py")
            pdfbrute_path = os.path.join(path, "pdfbrute.py")
            
            if os.path.exists(office2john_path) and not office2john_found:
                self.log_output(f"✓ Found office2john.py at: {office2john_path}")
                office2john_found = True
                
            # Check for current directory pdfbrute.py
            if path == os.getcwd():
                pdfbrute_path = os.path.join(path, "pdfbrute.py")
                if os.path.exists(pdfbrute_path) and not pdfbrute_found:
                    self.log_output(f"✓ Found pdfbrute.py at: {pdfbrute_path}")
                    pdfbrute_found = True
            
            if office2john_found and pdfbrute_found:
                break
        
        if not office2john_found:
            self.log_output("✗ office2john.py not found. Office document cracking may be less effective.")
            self.log_output("  Download from: https://raw.githubusercontent.com/openwall/john/bleeding-jumbo/run/office2john.py")
            
        if not pdfbrute_found:
            self.log_output("✗ pdfbrute.py not found. PDF bruteforce capabilities will be limited.")
            self.log_output("  Make sure pdfbrute.py is in the application directory for enhanced PDF cracking.")
            
        self.log_output("Extraction tools check completed.")
    
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
    
    def toggle_cracking(self, mode):
        """Toggle between starting and stopping the cracking process"""
        if self.is_cracking:
            self.stop_cracking()
        else:
            self.start_cracking(mode)
    
    def start_cracking(self, mode):
        """Start the password cracking process"""
        # Check current tab and attack type
        current_tab = self.tab_control.tab(self.tab_control.select(), "text")
        is_bruteforce = False
        
        # Determine if we're in bruteforce mode based on the tab
        if current_tab == "Office Documents" and hasattr(self, 'office_attack_type'):
            is_bruteforce = self.office_attack_type.get() == "Bruteforce"
        elif current_tab == "PDF Documents" and hasattr(self, 'pdf_attack_type'):
            is_bruteforce = self.pdf_attack_type.get() == "Bruteforce"
        elif current_tab == "NTLM Hash" and hasattr(self, 'hash_attack_type'):
            is_bruteforce = self.hash_attack_type.get() == "Bruteforce"
        
        # If we're using bruteforce, prompt for options
        if is_bruteforce:
            # For PDF tab, use the PDF-specific bruteforce options dialog
            if current_tab == "PDF Documents":
                # Set the UI to cracking state before showing the options dialog
                # This will change the button to "Stop Cracking"
                self.is_cracking = True
                self.update_crack_buttons("Stop Cracking")
                
                # PDF bruteforce settings are handled in the _crack_pdf method
                # The _crack_pdf method will reset the state if the user cancels in the dialog
                self._crack_pdf()
                return
            else:
                # For other tabs, use the generic bruteforce options
                if not self.prompt_bruteforce_length():
                    return  # User cancelled the operation
        
        # Only check for password list if not using bruteforce
        if not is_bruteforce and not self.password_list_path.get():
            messagebox.showerror("Error", "Please select a password list file")
            return
        
        if not self.target_file_path.get():
            messagebox.showerror("Error", "Please select a target file to crack")
            return
        
        if not self.hashcat_path and not self.check_hashcat():
            messagebox.showerror("Error", "Hashcat is required but not installed")
            return
        
        # Set the UI to cracking state
        self.is_cracking = True
        self.update_crack_buttons("Stop Cracking")
        
        thread = threading.Thread(target=self._run_cracking_process, args=(mode,))
        thread.daemon = True
        thread.start()
    
    def stop_cracking(self):
        """Stop the currently running cracking process"""
        if self.cracking_process and hasattr(self.cracking_process, 'poll') and self.cracking_process.poll() is None:
            self.log_output("Stopping cracking process...")
            if sys.platform == "win32":
                # On Windows, we need to use taskkill to kill the process and its children
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.cracking_process.pid)], 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                # On Unix-like systems, we can use terminate() or kill()
                self.cracking_process.terminate()
                try:
                    self.cracking_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.cracking_process.kill()
            
            self.log_output("Cracking process stopped by user.")
        elif isinstance(self.cracking_process, threading.Thread) and self.cracking_process.is_alive():
            # For threaded processes (like PDF bruteforce)
            self.log_output("Stopping PDF bruteforce process...")
            self.is_cracking = False  # This flag is checked in the thread loop
            
            # Set the stopped flag in the PDFBruteForcer instance if it exists
            if hasattr(self, 'pdf_brute_forcer') and self.pdf_brute_forcer is not None:
                self.pdf_brute_forcer.stopped = True
                self.log_output("Signaled PDF bruteforce to stop.")
            
            self.log_output("PDF bruteforce process stopped by user.")
        
        # Reset the cracking state
        self.is_cracking = False
        self.cracking_process = None
        self.update_crack_buttons("Start Cracking")
    
    def update_crack_buttons(self, text):
        """Update all crack buttons with the given text"""
        if hasattr(self, 'office_crack_button'):
            self.office_crack_button.config(text=text)
        if hasattr(self, 'pdf_crack_button'):
            self.pdf_crack_button.config(text=text)
        if hasattr(self, 'hash_crack_button'):
            self.hash_crack_button.config(text=text)

    def prompt_bruteforce_length(self):
        """Prompt the user for the bruteforce password length and character set"""
        # Create a dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Bruteforce Settings")
        dialog.transient(self.root)  # Make dialog modal
        dialog.grab_set()  # Make dialog modal
        
        # Center the dialog on the main window
        window_width = 400
        window_height = 350  # Increased height to fit all content
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        center_x = int(screen_width/2 - window_width/2)
        center_y = int(screen_height/2 - window_height/2)
        dialog.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        dialog.resizable(False, False)
        
        # Apply theme to dialog
        if self.is_dark_mode.get():
            dialog.configure(bg='#2E2E2E')
        else:
            dialog.configure(bg='#F0F0F0')
        
        # Add a frame for content
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add a label for length
        ttk.Label(frame, text="Enter maximum password length:").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 15))
        
        # Add a spinbox for password length
        length_var = tk.IntVar(value=self.bruteforce_length.get())
        length_spinbox = ttk.Spinbox(frame, from_=1, to=12, textvariable=length_var, width=5)
        length_spinbox.grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(frame, text="characters").grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Character set options section
        ttk.Label(frame, text="Character sets to include:", font=("Helvetica", 10, "bold")).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(15, 5))
        
        # Create character set checkboxes
        lowercase_cb = ttk.Checkbutton(frame, text="Lowercase letters (a-z)", variable=self.use_lowercase)
        lowercase_cb.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        uppercase_cb = ttk.Checkbutton(frame, text="Uppercase letters (A-Z)", variable=self.use_uppercase)
        uppercase_cb.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        digits_cb = ttk.Checkbutton(frame, text="Numbers (0-9)", variable=self.use_digits)
        digits_cb.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        special_cb = ttk.Checkbutton(frame, text="Special characters (!@#$...)", variable=self.use_special)
        special_cb.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # Warning message about bruteforce time
        warning_text = "Warning: Higher values and more character sets will significantly increase cracking time."
        warning_label = ttk.Label(frame, text=warning_text, foreground='red', wraplength=350)
        warning_label.grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=15)
        
        # Button frame
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=8, column=0, columnspan=2, pady=(15, 0))
        
        # Result variable
        result = tk.BooleanVar(value=False)
        
        # OK and Cancel buttons
        def on_ok():
            # Check if at least one character set is selected
            if not (self.use_lowercase.get() or self.use_uppercase.get() or 
                    self.use_digits.get() or self.use_special.get()):
                messagebox.showerror("Error", "Please select at least one character set")
                return
                
            self.bruteforce_length.set(length_var.get())
            result.set(True)
            dialog.destroy()
            
        def on_cancel():
            result.set(False)
            dialog.destroy()
        
        ttk.Button(button_frame, text="OK", command=on_ok, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=on_cancel, width=10).pack(side=tk.LEFT, padx=5)
        
        # Focus on the spinbox
        length_spinbox.focus_set()
        
        # Wait for the dialog to be closed
        self.root.wait_window(dialog)
        
        # Return whether the user clicked OK or Cancel
        return result.get()

    def get_bruteforce_mask(self):
        """Generate a hashcat mask based on selected character sets"""
        mask = ""
        
        if self.use_lowercase.get():
            mask += "?l"  # Lowercase letters
        
        if self.use_uppercase.get():
            mask += "?u"  # Uppercase letters
        
        if self.use_digits.get():
            mask += "?d"  # Digits
        
        if self.use_special.get():
            mask += "?s"  # Special characters
        
        # If no character sets were selected, default to lowercase
        if not mask:
            mask = "?l"
        
        # Repeat the mask for the specified length
        max_length = self.bruteforce_length.get()
        return mask * max_length

    def _run_cracking_process(self, mode):
        self.log_output(f"Starting {mode} password cracking...")
        self.log_output(f"Target file: {self.target_file_path.get()}")
        self.log_output(f"Password list: {self.password_list_path.get()}")
        
        try:
            if mode == "office":
                self._crack_office()
            elif mode == "pdf":
                # PDF bruteforce with options dialog is handled directly from start_cracking
                # This path is for non-bruteforce PDF cracking (dictionary attack)
                if not self.is_cracking:
                    # This means start_cracking has already handled it (PDF bruteforce case)
                    return
                else:
                    self._crack_pdf()
            elif mode == "hash":
                self._crack_hash()
        finally:
            # Ensure we reset the UI state when cracking is done or fails
            if self.is_cracking:  # Only update if we're still in cracking mode (not manually stopped)
                self.is_cracking = False
                self.cracking_process = None
                self.root.after(0, lambda: self.update_crack_buttons("Start Cracking"))
    
    def _crack_office(self):
        target_file = self.target_file_path.get()
        
        # Create hashes directory structure if it doesn't exist
        hashes_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hashes")
        office_hashes_dir = os.path.join(hashes_root, "office")
        os.makedirs(office_hashes_dir, exist_ok=True)
        
        # Generate a unique hash filename based on the target file name
        target_filename = os.path.basename(target_file)
        hash_filename = f"{os.path.splitext(target_filename)[0]}_hash.txt"
        hash_file = os.path.join(office_hashes_dir, hash_filename)
        
        # Check if using bruteforce mode
        is_bruteforce = self.office_attack_type.get() == "Bruteforce"
        if is_bruteforce:
            self.log_output("Using bruteforce attack mode", "info")
        
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
                    # Save the hash to the dedicated hashes directory
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
            if is_bruteforce:
                # Use bruteforce attack (attack mode 3) with a mask
                # Create a mask based on the user-specified options
                mask = self.get_bruteforce_mask()
                max_length = self.bruteforce_length.get()
                
                # Get the character set description for logging
                char_sets = []
                if self.use_lowercase.get(): char_sets.append("lowercase")
                if self.use_uppercase.get(): char_sets.append("uppercase")
                if self.use_digits.get(): char_sets.append("numbers")
                if self.use_special.get(): char_sets.append("special chars")
                
                command.extend(["-a", "3", hash_file, mask, "--increment"])
                self.log_output(f"Using bruteforce with mask: {mask} (max length: {max_length}, character sets: {', '.join(char_sets)})", "info")
            else:
                # Use dictionary attack (attack mode 0)
                command.extend(["-a", "0", hash_file, self.password_list_path.get()])
        else:
            self.log_output("No hash extracted. Attempting direct cracking...", "info")
            if is_bruteforce:
                # Use bruteforce attack (attack mode 3) with a mask
                mask = "?a?a?a?a?a?a?a?a"  # Default 8-char mask
                command.extend(["-m", "9600", "-a", "3", target_file, mask, "--increment", "--force"])
                self.log_output("Using bruteforce with mask: " + mask, "info")
            else:
                # Use dictionary attack (attack mode 0)
                command.extend(["-m", "9600", "-a", "0", target_file, self.password_list_path.get(), "--force"])
        
        # Add optimizations for bruteforce
        if is_bruteforce:
            command.extend(["--workload-profile", "3"])  # Better performance
            command.extend(["--optimized-kernel-enable"])
            # For bruteforce, use stdin pipe for possible interactive use
            use_pipe = True
            self.log_output("Note: This may take a long time for complex passwords!", "warning")
        else:
            use_pipe = False
        
        # Redirect output to a file in the same directory as the hash
        outfile_path = os.path.join(office_hashes_dir, f"{os.path.splitext(target_filename)[0]}_cracked.txt").replace('\\', '/')
        command.extend(["--outfile", outfile_path])
        if "--force" not in command:
            command.append("--force")
        self.log_output(f"Executing command: {' '.join(command)}")
        hashcat_dir = os.path.dirname(self.hashcat_path) if os.path.dirname(self.hashcat_path) else None
        
        try:
            if use_pipe:
                self.cracking_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, text=True, bufsize=1, cwd=hashcat_dir)
            else:
                self.cracking_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=hashcat_dir)
                
            for line in iter(self.cracking_process.stdout.readline, ''):
                if not self.is_cracking:  # If process was stopped by user
                    break
                self.log_output(line.strip())
            
            if self.is_cracking:  # Only process output if we haven't been manually stopped
                self.cracking_process.wait()
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
                    self._save_cracked_password(target_file, recovered_password)
                    # Show success message box
                    messagebox.showinfo("Success!", f"Password found: {recovered_password}")
                else:
                    self.log_output("Password not found or could not parse output.", is_password=True)
        except Exception as e:
            self.log_output(f"Error executing hashcat command: {str(e)}")
            self.log_output("Command that failed: " + " ".join(command))
    
    def _crack_pdf(self):
        # PDF cracking method using PyMuPDF (fitz) and hash extraction
        pdf_path = self.target_file_path.get().strip()
        wordlist_path = self.password_list_path.get().strip()
        
        if not pdf_path:
            messagebox.showerror("Error", "Please select a PDF file!")
            # Reset the button if we can't proceed
            if self.is_cracking:
                self.is_cracking = False
                self.update_crack_buttons("Start Cracking")
            return
        
        # Create hashes directory structure if it doesn't exist
        hashes_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hashes")
        pdf_hashes_dir = os.path.join(hashes_root, "pdf")
        os.makedirs(pdf_hashes_dir, exist_ok=True)
        
        # Generate a unique hash filename based on the target file name
        target_filename = os.path.basename(pdf_path)
        hash_filename = f"{os.path.splitext(target_filename)[0]}_hash.txt"
        hash_file = os.path.join(pdf_hashes_dir, hash_filename)
        
        # Check if using bruteforce mode
        is_bruteforce = self.pdf_attack_type.get() == "Bruteforce" if hasattr(self, 'pdf_attack_type') else False
        
        # We'll only open this path during direct button clicks, not from _run_cracking_process 
        # since we're handling that separately now
        if is_bruteforce:
            self.log_output("Using bruteforce attack mode for PDF", "info")
            
            # Check if PDFBruteForcer is available
            if PDFBruteForcer is None:
                self.log_output("Error: PDFBruteForcer not available. Using fallback method.")
                messagebox.showerror("Error", "PDF bruteforce module not available. Using fallback method.")
                # Fall back to the existing bruteforce method
                self._crack_pdf_hashcat_bruteforce(pdf_path, hash_file)
                return
                
            # Prompt for PDF-specific bruteforce options
            options = self.prompt_pdf_bruteforce_options()
            if not options:
                self.log_output("PDF bruteforce cancelled by user.")
                # The on_cancel method in the options dialog will reset the button state
                return
            
            # Set up PDFBruteForcer
            options['progress_file'] = os.path.join(pdf_hashes_dir, f"{os.path.splitext(target_filename)[0]}_progress.json")
            
            # Configure PDFBruteForcer to use our logging function
            options['log_function'] = lambda msg: self.root.after(10, lambda: self.log_output(msg))
            
            # Variable to store the brute forcer instance
            self.pdf_brute_forcer = None
            
            # Create a thread to run the bruteforce process
            def run_pdf_bruteforce():
                try:
                    self.log_output(f"Starting PDF bruteforce with {options['library']} library...")
                    self.log_output(f"Password length: {options['min_length']} to {options['max_length']} characters")
                    self.log_output(f"Character set: {options['charset']}")
                    
                    # Initialize PDFBruteForcer with our logging function
                    self.pdf_brute_forcer = PDFBruteForcer(pdf_path, options)
                    
                    # Run the bruteforce attack
                    try:
                        success = self.pdf_brute_forcer.run()
                        
                        if not self.is_cracking:  # If stopped by user
                            self.log_output("PDF bruteforce stopped by user.")
                            return
                        
                        if success and self.pdf_brute_forcer.found_password:
                            self.log_output(f"PDF password cracking completed successfully!", is_password=True)
                            self.log_output(f"PASSWORD FOUND: {self.pdf_brute_forcer.found_password}", is_password=True)
                            self._save_cracked_password(pdf_path, self.pdf_brute_forcer.found_password)
                            # Show success message box
                            messagebox.showinfo("Success!", f"Password found: {self.pdf_brute_forcer.found_password}")
                        else:
                            self.log_output("Password not found. Exhausted all combinations.", is_password=True)
                    except KeyboardInterrupt:
                        self.log_output("PDF bruteforce stopped by user.")
                    except Exception as e:
                        self.log_output(f"Error in PDF bruteforce: {str(e)}")
                except Exception as e:
                    self.log_output(f"Error initializing PDF bruteforce: {str(e)}")
                
                # Reset the cracking state after completion (only if not already done by user stopping)
                if self.is_cracking:
                    self.is_cracking = False
                    self.root.after(0, lambda: self.update_crack_buttons("Start Cracking"))
            
            # Start the bruteforce process in a thread
            self.log_output("Starting PDF bruteforce thread...")
            self.cracking_process = threading.Thread(target=run_pdf_bruteforce)
            self.cracking_process.daemon = True
            self.cracking_process.start()
            return
            
        # Non-bruteforce (dictionary attack) case
        # At this point, we know we're doing a dictionary attack, so require wordlist
        if not wordlist_path:
            messagebox.showerror("Error", "Please select a wordlist for dictionary attack!")
            # Reset the button if we can't proceed
            if self.is_cracking:
                self.is_cracking = False
                self.update_crack_buttons("Start Cracking")
            return
        
        # If not bruteforce, use dictionary attack with PyMuPDF
        try:
            with open(wordlist_path, "r", encoding="latin-1", errors='ignore') as f:
                passwords = f.readlines()
            
            pdf_doc = fitz.open(pdf_path)
            found = False
            for password in passwords:
                if not self.is_cracking:  # Check if process was stopped
                    break
                
                password = password.strip()
                self.log_output(f"Trying password: {password}")
                self.root.update()  # Allow GUI to update
                
                if pdf_doc.authenticate(password):
                    messagebox.showinfo("Success!", f"Password found: {password}")
                    self.log_output(f"PDF password cracking completed successfully! PASSWORD FOUND: {password}", is_password=True)
                    self._save_cracked_password(pdf_path, password)
                    found = True
                    break
            
            if self.is_cracking and not found:  # Only show message if we weren't manually stopped
                messagebox.showerror("Failed", "No password in dictionary matched!")
                self.log_output("No password in dictionary matched!")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")
            self.log_output(f"Error in PDF cracking: {e}")
    
    def _crack_pdf_hashcat_bruteforce(self, pdf_path, hash_file):
        """Fallback method using hashcat for PDF bruteforce if PDFBruteForcer is not available"""
        target_filename = os.path.basename(pdf_path)
        pdf_hashes_dir = os.path.dirname(hash_file)
        
        # Use direct hashcat PDF cracking approach
        try:
            self.log_output("Using direct hashcat method for PDF bruteforce...")
            
            # Create a simple hash file with the PDF file path
            with open(hash_file, 'w') as f:
                f.write(pdf_path)
            
            # Use hashcat to crack the PDF directly
            command = [self.hashcat_path if os.path.dirname(self.hashcat_path)
                      else ("hashcat.exe" if sys.platform=="win32" else "hashcat")]
            
            # PDF hash mode for hashcat is 10500 (PDF 1.1-1.3) or 10600 (PDF 1.4-1.6)
            # Use 10700 as a more universal option that handles different PDF versions
            # Create a mask based on the user-specified options
            mask = self.get_bruteforce_mask()
            max_length = self.bruteforce_length.get()
            
            # Get the character set description for logging
            char_sets = []
            if self.use_lowercase.get(): char_sets.append("lowercase")
            if self.use_uppercase.get(): char_sets.append("uppercase")
            if self.use_digits.get(): char_sets.append("numbers")
            if self.use_special.get(): char_sets.append("special chars")
            
            command.extend(["-m", "10700", "-a", "3", hash_file, mask, "--increment"])
            self.log_output(f"Using bruteforce with mask: {mask} (max length: {max_length}, character sets: {', '.join(char_sets)})", "info")
            
            # Add optimizations for bruteforce
            command.extend(["--workload-profile", "3"])  # Better performance
            command.extend(["--optimized-kernel-enable"])
            
            # Redirect output to a file in the same directory as the hash
            outfile_path = os.path.join(pdf_hashes_dir, f"{os.path.splitext(target_filename)[0]}_cracked.txt").replace('\\', '/')
            command.extend(["--outfile", outfile_path, "--force"])
            
            self.log_output(f"Executing command: {' '.join(command)}")
            hashcat_dir = os.path.dirname(self.hashcat_path) if os.path.dirname(self.hashcat_path) else None
            
            self.cracking_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                                    stdin=subprocess.PIPE, text=True, bufsize=1, cwd=hashcat_dir)
            
            for line in iter(self.cracking_process.stdout.readline, ''):
                if not self.is_cracking:  # If process was stopped by user
                    break
                self.log_output(line.strip())
            
            if self.is_cracking:  # Only process output if we haven't been manually stopped
                self.cracking_process.wait()
                # Run --show command to retrieve the password
                show_cmd = [self.hashcat_path, "-m", "10700", "--show", hash_file]
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
                    self._save_cracked_password(pdf_path, recovered_password)
                    # Show success message box
                    messagebox.showinfo("Success!", f"Password found: {recovered_password}")
                else:
                    self.log_output("Password not found or could not parse output.", is_password=True)
            return
        except Exception as e:
            self.log_output(f"Error in PDF hash extraction: {str(e)}")
            messagebox.showerror("Error", f"Error extracting PDF hash: {str(e)}")
    
    def prompt_pdf_bruteforce_options(self):
        """Display a dialog for PDF-specific bruteforce settings"""
        # Create a dialog with ttk styling to match the application
        options = {}
        
        # Create a dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("PDF Bruteforce Settings")
        
        # Set a fixed size with reasonable dimensions
        dialog.geometry("450x600")
        dialog.resizable(False, False)
        
        # Apply theme
        bg_color = '#2E2E2E' if self.is_dark_mode.get() else '#F0F0F0'
        dialog.configure(bg=bg_color)
        
        # Create variables for options
        min_length_var = tk.IntVar(value=1)
        max_length_var = tk.IntVar(value=8)
        charset_var = tk.StringVar(value="digits")
        use_digits_var = tk.BooleanVar(value=True)
        use_lower_var = tk.BooleanVar(value=False)
        use_upper_var = tk.BooleanVar(value=False)
        use_special_var = tk.BooleanVar(value=False)
        library_var = tk.StringVar(value=AVAILABLE_LIBRARIES[0][0] if AVAILABLE_LIBRARIES else "")
        
        # Main content frame with ttk styling
        main_frame = ttk.Frame(dialog, padding=(15, 10))
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title with ttk styling
        ttk.Label(main_frame, text="PDF Bruteforce Settings", 
                font=("Helvetica", 12, "bold")).pack(anchor=tk.W, pady=(0, 15))
        
        # Password length section
        length_frame = ttk.LabelFrame(main_frame, text="Password Length", padding=(10, 5))
        length_frame.pack(fill=tk.X, pady=8)
        
        # Min length
        min_frame = ttk.Frame(length_frame)
        min_frame.pack(fill=tk.X, padx=10, pady=3)
        ttk.Label(min_frame, text="Minimum Length:").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Spinbox(min_frame, from_=1, to=12, textvariable=min_length_var, width=5).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # Max length
        max_frame = ttk.Frame(length_frame)
        max_frame.pack(fill=tk.X, padx=10, pady=3)
        ttk.Label(max_frame, text="Maximum Length:").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Spinbox(max_frame, from_=1, to=12, textvariable=max_length_var, width=5).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # Character set section with ttk styling
        charset_frame = ttk.LabelFrame(main_frame, text="Character Set", padding=(10, 5))
        charset_frame.pack(fill=tk.X, pady=8)
        
        # Character set options
        ttk.Radiobutton(charset_frame, text="Digits only (0-9)", 
                       variable=charset_var, value="digits").pack(anchor=tk.W, padx=10, pady=2)
        
        ttk.Radiobutton(charset_frame, text="Letters (a-z, A-Z)", 
                       variable=charset_var, value="letters").pack(anchor=tk.W, padx=10, pady=2)
        
        ttk.Radiobutton(charset_frame, text="Alphanumeric (letters + digits)", 
                       variable=charset_var, value="alphanum").pack(anchor=tk.W, padx=10, pady=2)
        
        ttk.Radiobutton(charset_frame, text="All characters (including symbols)", 
                       variable=charset_var, value="all").pack(anchor=tk.W, padx=10, pady=2)
        
        # Custom charset option
        custom_radio = ttk.Radiobutton(charset_frame, text="Custom combination:", 
                                      variable=charset_var, value="custom")
        custom_radio.pack(anchor=tk.W, padx=10, pady=(8, 2))
        
        # Custom charset checkboxes in their own frame
        custom_frame = ttk.Frame(charset_frame, padding=(20, 0, 0, 0))
        custom_frame.pack(fill=tk.X, pady=2)
        
        # Two columns for checkboxes
        ttk.Checkbutton(custom_frame, text="Digits (0-9)", 
                       variable=use_digits_var).grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        
        ttk.Checkbutton(custom_frame, text="Lowercase (a-z)", 
                       variable=use_lower_var).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Checkbutton(custom_frame, text="Uppercase (A-Z)", 
                       variable=use_upper_var).grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        
        ttk.Checkbutton(custom_frame, text="Symbols (!@#$...)", 
                       variable=use_special_var).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Library section with ttk styling
        library_frame = ttk.LabelFrame(main_frame, text="PDF Library", padding=(10, 5))
        library_frame.pack(fill=tk.X, pady=8)
        
        # Create combobox for library selection
        if AVAILABLE_LIBRARIES:
            ttk.Label(library_frame, text="Select library:").pack(anchor=tk.W, padx=10, pady=2)
            library_combo = ttk.Combobox(library_frame, textvariable=library_var, 
                                       values=[lib for lib, _ in AVAILABLE_LIBRARIES],
                                       state="readonly", width=30)
            library_combo.pack(anchor=tk.W, padx=10, pady=2)
            library_combo.current(0)
        else:
            ttk.Label(library_frame, text="No PDF libraries available", 
                    foreground="red").pack(padx=10, pady=5)
        
        # Warning message with ttk styling
        warning_frame = ttk.Frame(main_frame)
        warning_frame.pack(fill=tk.X, pady=10)
        warning_label = ttk.Label(warning_frame, 
                                text="Warning: Higher values and more character sets\nwill significantly increase cracking time.",
                                foreground="red")
        warning_label.pack(anchor=tk.W)
        
        # Result variable
        result = [None]
        
        # Create a more subtle but still visible button container
        button_container = ttk.Frame(dialog, padding=(15, 10, 15, 15))
        button_container.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Add a separator above the buttons for visual distinction
        ttk.Separator(dialog, orient='horizontal').pack(side=tk.BOTTOM, fill=tk.X, before=button_container)
        
        # Button callbacks
        def on_ok():
            # Validate settings
            min_len = min_length_var.get()
            max_len = max_length_var.get()
            
            if min_len > max_len:
                messagebox.showerror("Error", "Minimum length cannot be greater than maximum length")
                return
                
            # Construct custom charset if selected
            charset = charset_var.get()
            if charset == "custom":
                custom_charset = ""
                if use_digits_var.get(): custom_charset += "d"
                if use_lower_var.get(): custom_charset += "l"
                if use_upper_var.get(): custom_charset += "u" 
                if use_special_var.get(): custom_charset += "s"
                
                if not custom_charset:
                    messagebox.showerror("Error", "Please select at least one character set")
                    return
                    
                charset = custom_charset
            
            # Construct options
            options = {
                'min_length': min_len,
                'max_length': max_len,
                'charset': charset,
                'library': library_var.get(),
                'save_progress': True,
                'show_progress_every': 1000
            }
            
            # Keep the button in "Stop Cracking" state because we're proceeding with cracking
            # The is_cracking flag should already be set to True before this dialog opened
            
            result[0] = options
            dialog.destroy()
                
        def on_cancel():
            # Reset the cracking state since the user is cancelling
            self.is_cracking = False
            self.update_crack_buttons("Start Cracking")
            
            result[0] = None
            dialog.destroy()
        
        # Normal sized ttk buttons but with sufficient padding
        ok_button = ttk.Button(button_container, text="Start Bruteforce", command=on_ok, width=16)
        ok_button.pack(side=tk.LEFT, padx=(0, 5), pady=5)
        
        cancel_button = ttk.Button(button_container, text="Cancel", command=on_cancel, width=16)
        cancel_button.pack(side=tk.RIGHT, padx=(5, 0), pady=5)
        
        # Make the dialog modal
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.focus_set()
        
        # Wait for the dialog to be closed
        self.root.wait_window(dialog)
        
        # Return the options
        return result[0]
    
    def _crack_hash(self):
        target_file = self.target_file_path.get()
        
        # Create hashes directory structure if it doesn't exist
        hashes_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hashes")
        ntlm_hashes_dir = os.path.join(hashes_root, "ntlm")
        os.makedirs(ntlm_hashes_dir, exist_ok=True)
        
        # Generate a unique hash filename based on the target file name
        target_filename = os.path.basename(target_file) if os.path.exists(target_file) else "hash_input.txt"
        hash_filename = f"{os.path.splitext(target_filename)[0]}_processed.txt"
        hash_file = os.path.join(ntlm_hashes_dir, hash_filename)
        
        # Raw hash filename for direct hashcat input (without formatting)
        raw_hash_filename = f"{os.path.splitext(target_filename)[0]}_raw.txt"
        raw_hash_file = os.path.join(ntlm_hashes_dir, raw_hash_filename)
        
        # Check if using bruteforce mode
        is_bruteforce = self.hash_attack_type.get() == "Bruteforce" if hasattr(self, 'hash_attack_type') else False
        
        # Determine the hash type based on the selection in the dropdown
        selected_hash_type = self.hash_type_combo.get() if hasattr(self, 'hash_type_combo') else "NTLM"
        
        # Map the selected hash type to the appropriate hashcat mode
        hash_mode_map = {
            "NTLM": "1000",      # NTLM
            "NTLMv2": "5600",    # NetNTLMv2
            "NetNTLM": "5500",   # NetNTLM
            "NetNTLMv2": "5600"  # NetNTLMv2
        }
        
        # Get the hash mode from the map, default to NTLM (1000) if not found
        hash_mode = hash_mode_map.get(selected_hash_type, "1000")
        
        self.log_output(f"Using hash type: {selected_hash_type} (Hashcat mode: {hash_mode})")
        
        # Read the hash content
        if os.path.exists(target_file):
            # Read hash content from file
            with open(target_file, 'r') as src_file:
                hash_content = src_file.read().strip()
        else:
            # If target_file doesn't exist, it might be direct hash input
            hash_content = target_file.strip()
        
        self.log_output(f"Processing hash input: {hash_content[:50]}..." if len(hash_content) > 50 else f"Processing hash input: {hash_content}")
            
        # Try to identify hash format and extract the actual hash value
        if "Admin:" in hash_content or "..." in hash_content:
            # This appears to be the format seen in the user's error message
            processed_content = hash_content
            
            # If selected hash type is NTLM, extract just the NTLM hash part
            # For NetNTLMv2, we need to keep the full format: username::domain:challenge:hash:other
            if selected_hash_type == "NTLM":
                # Extract the NTLM hash (32 hex characters)
                import re
                ntlm_hashes = re.findall(r'[0-9a-fA-F]{32}', hash_content)
                if ntlm_hashes:
                    processed_content = ntlm_hashes[0]
                    self.log_output(f"Extracted NTLM hash: {processed_content}")
                else:
                    # If no valid hash is found, just use the raw content
                    self.log_output("Could not extract NTLM hash, using raw content instead")
            elif selected_hash_type in ["NetNTLMv2", "NTLMv2"]:
                # Ensure the hash is in the correct format for NetNTLMv2
                # Expected format: username::domain:challenge:NTLM response:other data
                if "::" in hash_content and hash_content.count(":") >= 4:
                    # Hash is already properly formatted
                    self.log_output(f"Hash appears to be properly formatted for {selected_hash_type}")
                else:
                    # Try to extract components and reformat
                    try:
                        # Common format seen in packet captures: Admin::RazerBlade:493a76dae1a6e269:4D5C2CB820D5A6F5319368E76F825079
                        # Expected by hashcat: username::domain:challenge:NTLMV2 hash:blob
                        
                        # This specific format is commonly seen in Wireshark exports
                        regex_pattern = r'([^:]+)::([^:]+):([0-9a-f]+):([0-9a-fA-F]+)'
                        match = re.match(regex_pattern, hash_content)
                        
                        if match:
                            username = match.group(1)
                            domain = match.group(2)
                            challenge = match.group(3)
                            hash_value = match.group(4)
                            
                            # Create a properly formatted NetNTLMv2 hash with the blob part
                            # If the hash value is longer than 32 chars, split it
                            if len(hash_value) > 32:
                                ntlm_hash = hash_value[:32]
                                blob = hash_value[32:]
                                processed_content = f"{username}::{domain}:{challenge}:{ntlm_hash}:{blob}"
                            else:
                                # If we only have the hash part, add a placeholder for the blob
                                processed_content = f"{username}::{domain}:{challenge}:{hash_value}:any"
                                
                            self.log_output(f"Reformatted NetNTLMv2 hash: {processed_content}")
                        
                        # If the specific pattern doesn't match, try the more general approaches
                        # First check for the simple case with separate challenge and hash
                        parts = re.split(r'[:]+', hash_content)
                        if len(parts) >= 4:
                            username = parts[0]
                            domain = parts[2] if len(parts) > 2 else "domain"
                            challenge = parts[3] if len(parts) > 3 else ""
                            ntlm_hash = parts[4] if len(parts) > 4 else ""
                            
                            # If the challenge part looks like a challenge but we don't have the hash part
                            # Sometimes the hash format is username::domain:challenge+hash
                            if not ntlm_hash and len(challenge) > 32:
                                # Try to split the challenge+hash part
                                if len(challenge) > 16:
                                    ntlm_hash = challenge[16:]
                                    challenge = challenge[:16]
                            
                            # If we found all the required parts
                            if username and challenge and ntlm_hash:
                                # Create a properly formatted NetNTLMv2 hash
                                processed_content = f"{username}::{domain}:{challenge}:{ntlm_hash}:any"
                                self.log_output(f"Reformatted hash for {selected_hash_type}: {processed_content}")
                            else:
                                import re
                                username_match = re.search(r'([^:]+):', hash_content)
                                domain_match = re.search(r':([\w\-]+):', hash_content)
                                challenge_match = re.search(r':([0-9a-f]{16}):', hash_content, re.IGNORECASE)
                                hash_match = re.search(r':([0-9a-f]{32})', hash_content, re.IGNORECASE)
                                
                                if username_match and challenge_match and hash_match:
                                    username = username_match.group(1)
                                    domain = domain_match.group(1) if domain_match else "domain"
                                    challenge = challenge_match.group(1)
                                    hash_value = hash_match.group(1)
                                    
                                    # Create a properly formatted NetNTLMv2 hash
                                    processed_content = f"{username}::{domain}:{challenge}:{hash_value}:any"
                                    self.log_output(f"Reformatted hash for {selected_hash_type}: {processed_content}")
                                else:
                                    self.log_output(f"Could not reformat hash for {selected_hash_type}. Using original format.")
                        else:
                            self.log_output(f"Could not reformat hash for {selected_hash_type}. Using original format.")
                    except Exception as e:
                        self.log_output(f"Error reformatting hash: {str(e)}. Using original format.")
            else:
                # For other hash types, preserve the original format
                self.log_output(f"Using original hash format for {selected_hash_type}")
        else:
            # Just basic processing to handle common formats
            processed_content = hash_content.strip()
            # For NTLM mode, extract just the hash if there's a username prefix
            if selected_hash_type == "NTLM" and ":" in processed_content:
                parts = processed_content.split(":", 1)
                processed_content = parts[1].strip()
                
        # Save both processed and raw versions
        with open(hash_file, 'w') as f:
            f.write(processed_content)
        
        with open(raw_hash_file, 'w') as f:
            f.write(hash_content)
            
        self.log_output(f"Processed hash saved to {hash_file}")
        
        # Set up the hashcat command
        command = [self.hashcat_path if os.path.dirname(self.hashcat_path)
                   else ("hashcat.exe" if sys.platform=="win32" else "hashcat")]
        
        # Define use_pipe variable
        use_pipe = False
        
        if is_bruteforce:
            # Use bruteforce attack (attack mode 3) with a mask
            # Create a mask based on the user-specified options
            mask = self.get_bruteforce_mask()
            max_length = self.bruteforce_length.get()
            
            # Get the character set description for logging
            char_sets = []
            if self.use_lowercase.get(): char_sets.append("lowercase")
            if self.use_uppercase.get(): char_sets.append("uppercase")
            if self.use_digits.get(): char_sets.append("numbers")
            if self.use_special.get(): char_sets.append("special chars")
            
            # Add appropriate flags for hash format
            command.extend(["-m", hash_mode, "-a", "3", hash_file, mask, "--increment"])
            
            self.log_output(f"Using bruteforce with mask: {mask} (max length: {max_length}, character sets: {', '.join(char_sets)})", "info")
            
            # For bruteforce, use stdin pipe for possible interactive use
            use_pipe = True
        else:
            # Validate wordlist path
            if not self.password_list_path.get():
                self.log_output("Error: No wordlist selected for dictionary attack.", "error")
                messagebox.showerror("Error", "Please select a wordlist for dictionary attack.")
                return
                
            # Make sure the wordlist exists
            if not os.path.exists(self.password_list_path.get()):
                self.log_output(f"Error: Selected wordlist not found: {self.password_list_path.get()}", "error")
                messagebox.showerror("Error", f"Selected wordlist not found: {self.password_list_path.get()}")
                return
                
            # Use dictionary attack (attack mode 0) with the selected wordlist directly
            command.extend(["-m", hash_mode, "-a", "0", hash_file, self.password_list_path.get()])
            self.log_output(f"Using dictionary attack with wordlist: {self.password_list_path.get()}")
        
        # Set output file in the hashes directory
        outfile_path = os.path.join(ntlm_hashes_dir, f"{os.path.splitext(target_filename)[0]}_cracked.txt").replace('\\', '/')
        command.extend(["--outfile", outfile_path])
        
        if "--force" not in command:
            command.append("--force")
            
        self.log_output(f"Executing command: {' '.join(command)}")
        hashcat_dir = os.path.dirname(self.hashcat_path) if os.path.dirname(self.hashcat_path) else None
        
        # Variable to track if a password was found
        found_password = None
        
        try:
            if use_pipe:
                self.cracking_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                                       stdin=subprocess.PIPE, text=True, bufsize=1, cwd=hashcat_dir)
            else:
                self.cracking_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                                       text=True, bufsize=1, cwd=hashcat_dir)
            
            # Process and display hashcat output
            for line in iter(self.cracking_process.stdout.readline, ''):
                if not self.is_cracking:  # If process was stopped by user
                    break
                    
                self.log_output(line.strip())
                
                # Check for potfile message
                if "All hashes found as potfile" in line:
                    self.log_output("Hash already cracked, checking potfile for password...", is_password=True)
                    # Get the password from the potfile
                    self._get_password_from_potfile(hash_file, selected_hash_type)
                    return
                
                # Look for password in the output
                if "Plain.Text." in line and ":" in line:
                    try:
                        # Extract the password part which comes after the colon in the Plain.Text section
                        parts = line.split("Plain.Text.", 1)[1].split(":", 1)
                        if len(parts) >= 2:
                            found_password = parts[1].strip()
                    except Exception:
                        # Fallback if the splitting fails
                        if ":" in line:
                            found_password = line.split(":", 1)[1].strip()
            
            # Wait for process to complete if still cracking
            if self.is_cracking:
                self.cracking_process.wait()
                
                # If we detected a cracked password directly from the output, report it
                if found_password:
                    self.log_output("Password cracking completed successfully!", is_password=True)
                    self.log_output(f"PASSWORD FOUND: {found_password}", is_password=True)
                    self._save_cracked_password(target_file, found_password)
                    # Show success message box
                    messagebox.showinfo("Success!", f"Password found: {found_password}")
                    return
                
                # If no password was detected in real-time, let's check if one was created
                # Sometimes hashcat finds a password but doesn't show it clearly in the output
                outfile_path = os.path.join(ntlm_hashes_dir, f"{os.path.splitext(target_filename)[0]}_cracked.txt")
                self.log_output("Checking for password in output files...")
                
                # Check if the outfile contains a password
                if os.path.exists(outfile_path) and os.path.getsize(outfile_path) > 0:
                    try:
                        with open(outfile_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().strip()
                            if content and ":" in content:
                                # For NetNTLMv2, the password is at the end after the last colon
                                password = content.split(":")[-1].strip()
                                if password:
                                    self.log_output("Password cracking completed successfully!", is_password=True)
                                    self.log_output(f"PASSWORD FOUND: {password}", is_password=True)
                                    self._save_cracked_password(target_file, password)
                                    # Show success message box
                                    messagebox.showinfo("Success!", f"Password found: {password}")
                                    return
                    except Exception as e:
                        self.log_output(f"Error reading output file: {str(e)}")
                
                # As a final check, run hashcat with --show to see if it finds anything in the potfile
                show_cmd = [self.hashcat_path, "-m", hash_mode, "--show", hash_file]
                self.log_output(f"Running final check with command: {' '.join(show_cmd)}")
                try:
                    show_result = subprocess.run(show_cmd, capture_output=True, text=True)
                    output = show_result.stdout.strip()
                    if output:
                        # Process based on hash type
                        if selected_hash_type in ["NetNTLMv2", "NTLMv2"] and ":" in output:
                            password = output.split(":")[-1].strip()
                            self.log_output("Password cracking completed successfully!", is_password=True)
                            self.log_output(f"PASSWORD FOUND: {password}", is_password=True)
                            self._save_cracked_password(target_file, password)
                            # Show success message box
                            messagebox.showinfo("Success!", f"Password found: {password}")
                            return
                except Exception as e:
                    self.log_output(f"Error running show command: {str(e)}")
                
                # If we get here, no password was found
                self.log_output("Password not found or could not be detected.", is_password=True)
        except Exception as e:
            self.log_output(f"Error executing hashcat command: {str(e)}")
            self.log_output("Command that failed: " + " ".join(command))
    
    def _save_cracked_password(self, target_file, password):
        try:
            save_path = os.path.join(os.path.dirname(target_file), "cracked_password.txt")
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(f"Target: {target_file}\nPassword: {password}")
            return password  # Return just the password itself
        except Exception as e:
            self.log_output(f"Note: Couldn't save password to file: {str(e)}")
            return password  # Still return the password even if saving fails
    
    def log_output(self, message, is_password=False):
        if self.output_text:
            if is_password:
                self.output_text.insert(tk.END, message + "\n", "password_found")
            else:
                self.output_text.insert(tk.END, message + "\n")
            self.output_text.see(tk.END)
            self.root.update_idletasks()

    def _on_office_attack_type_changed(self, event=None):
        """Handle when office attack type changes between dictionary and bruteforce"""
        attack_type = self.office_attack_type.get()
        
        # Update UI based on selected attack type
        if attack_type == "Bruteforce":
            # Make wordlist optional for bruteforce
            self.log_output("Bruteforce mode selected - password list is not used")
            
            # If in the office tab, we can update the UI to reflect the mode
            current_tab = self.tab_control.tab(self.tab_control.select(), "text")
            if current_tab == "Office Documents":
                # Visually disable the password list but don't block it completely
                # This allows flexibility but indicates it's not required
                for widget in self.lower_frame.winfo_children():
                    if isinstance(widget, ttk.Frame):  # Password list frame
                        for child in widget.winfo_children():
                            if isinstance(child, ttk.Entry):
                                child.state(['disabled'])
                            if isinstance(child, ttk.Button) and child.cget("text") == "Browse":
                                child.state(['disabled'])
        else:  # Dictionary Attack
            self.log_output("Dictionary Attack mode selected - password list is required")
            
            # Re-enable password list selector if it was disabled
            for widget in self.lower_frame.winfo_children():
                if isinstance(widget, ttk.Frame):  # Password list frame
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Entry):
                            child.state(['!disabled'])
                        if isinstance(child, ttk.Button) and child.cget("text") == "Browse":
                            child.state(['!disabled'])

    def _on_tab_changed(self, event):
        """Event handler for tab change to hide/show output based on active tab and save state"""
        current_tab = self.tab_control.tab(self.tab_control.select(), "text")
        previous_tab = getattr(self, '_previous_tab', None)
        self._previous_tab = current_tab

        # Always ensure proper reset of state before setting new state
        # This helps avoid inconsistencies when switching between tabs
        
        # First, reset the output frame visibility
        self.output_frame.pack_forget()
        
        # Then try to ensure the lower_frame is not managed by removing it from the paned window
        try:
            self.main_paned.remove(self.lower_frame)
        except Exception:
            pass
            
        # Now handle tab-specific behavior
        if current_tab in ["SSH File Browser", "Dictionary Manager", "About"]:
            # These tabs should have no lower frame - we've already removed it
            # Make the tab section expand to fill the entire window
            pass
        else:
            # All other tabs (Office, PDF, Hash) should show the lower frame with output area
            try:
                # Add back lower frame with proper weight
                self.main_paned.add(self.lower_frame, weight=1)
                
                # Make sure output frame is visible for these tabs
                self.output_frame.pack(fill=tk.BOTH, expand=True, pady=5)
                
                # Ensure the sash position gives enough room to the output area
                # Get a reasonable position (about 45-50% of window height)
                window_height = self.root.winfo_height()
                target_position = min(int(window_height * 0.4), 250)
                
                # Only set if our sash is too low (giving too little space to output)
                try:
                    current_pos = self.main_paned.sashpos(0)
                    if current_pos > window_height - 200:  # If sash is too low (output area too small)
                        self.main_paned.sashpos(0, target_position)
                        # Save this position in config
                        self.config['sash_position'] = target_position
                except Exception:
                    # If we can't get or set sash position, just try using our target
                    try:
                        self.main_paned.sashpos(0, target_position)
                    except Exception:
                        pass
            except Exception as e:
                print(f"Error setting up tab layout: {e}")
        
        # Save the current tab in the configuration
        self.save_window_config()
        
        # Force a UI refresh to ensure changes take effect
        self.root.update_idletasks()

    def _fix_combobox_display(self):
        """Apply fixes to ensure combobox arrows are displayed correctly on all platforms"""
        # This method is called after theme changes to ensure dropdown arrows are visible
        for tab in [self.office_tab, self.pdf_tab, self.hash_tab, self.dictionary_tab]:
            if tab:
                for child in tab.winfo_children():
                    if isinstance(child, ttk.LabelFrame):
                        for grandchild in child.winfo_children():
                            try:
                                if isinstance(grandchild, ttk.Combobox):
                                    # Ensure all comboboxes have readonly state for consistent appearance
                                    if grandchild.cget('state') != 'readonly':
                                        grandchild.config(state='readonly')
                            except Exception:
                                pass  # Skip widgets that can't be configured
        
        # Force update to ensure all widgets are rendered correctly
        self.root.update()
        self.root.update_idletasks()

    def clear_output(self):
        """Clear the output text area"""
        if self.output_text:
            self.output_text.delete(1.0, tk.END)
            self.log_output("Output cleared")

    def save_output(self):
        """Save the output text to a file"""
        if not self.output_text or not self.output_text.get(1.0, tk.END).strip():
            messagebox.showinfo("Info", "No output to save")
            return
        
        try:
            # Default file name with timestamp
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            default_filename = f"p4wnforge_output_{timestamp}.txt"
            
            # Get output directory path
            output_dir = os.path.join(os.path.expanduser("~"), ".p4wnforge", "logs")
            os.makedirs(output_dir, exist_ok=True)
            
            # Open save dialog
            filepath = filedialog.asksaveasfilename(
                title="Save Output",
                initialdir=output_dir,
                initialfile=default_filename,
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
            )
            
            if not filepath:
                return  # User cancelled
            
            # Save the output text
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.output_text.get(1.0, tk.END))
            
            self.log_output(f"Output saved to: {filepath}")
            messagebox.showinfo("Success", f"Output saved to:\n{filepath}")
        except Exception as e:
            error_msg = f"Error saving output: {str(e)}"
            self.log_output(error_msg)
            messagebox.showerror("Error", error_msg)

    def setup_ssh_tab(self):
        """Set up the SSH tab for remote file browsing and download"""
        ssh_frame = ttk.Frame(self.ssh_tab, padding="10")
        ssh_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create a top frame for connection settings and session management
        top_frame = ttk.Frame(ssh_frame)
        top_frame.pack(fill=tk.X, expand=False, pady=(0, 10))
        
        # Connection settings in a labeled frame
        conn_frame = ttk.LabelFrame(top_frame, text="SSH Connection", padding="10")
        conn_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # SSH connection parameters
        self.ssh_host = tk.StringVar(value="")
        self.ssh_port = tk.StringVar(value="22")
        self.ssh_username = tk.StringVar()
        self.ssh_password = tk.StringVar()
        self.ssh_current_dir = tk.StringVar(value="/")  # Current remote directory
        self.ssh_remember_password = tk.BooleanVar(value=False)  # Whether to save password
        self.ssh_session_name = tk.StringVar(value="")  # For saving/loading sessions
        
        # Session management in a labeled frame
        session_frame = ttk.LabelFrame(top_frame, text="Session Management", padding="10")
        session_frame.pack(side=tk.RIGHT, fill=tk.X, expand=False, padx=(10, 0))
        
        # Session selection combobox
        ttk.Label(session_frame, text="Saved Sessions:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.session_combo = FixedCombobox(session_frame, is_dark_mode_var=self.is_dark_mode, 
                                          textvariable=self.ssh_session_name, width=20)
        self.session_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Load saved sessions into combobox
        self.load_ssh_sessions()
        
        # Session management buttons
        session_buttons = ttk.Frame(session_frame)
        session_buttons.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Button(session_buttons, text="Load", command=self.load_ssh_session).pack(side=tk.LEFT, padx=5)
        ttk.Button(session_buttons, text="Save", command=self.save_ssh_session).pack(side=tk.LEFT, padx=5)
        ttk.Button(session_buttons, text="Delete", command=self.delete_ssh_session).pack(side=tk.LEFT, padx=5)
        
        # SSH connection fields in grid layout
        ttk.Label(conn_frame, text="Host:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(conn_frame, textvariable=self.ssh_host, width=20).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(conn_frame, textvariable=self.ssh_port, width=5).grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(conn_frame, text="Username:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(conn_frame, textvariable=self.ssh_username, width=20).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(conn_frame, text="Password:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        password_entry = ttk.Entry(conn_frame, textvariable=self.ssh_password, width=20, show="*")
        password_entry.grid(row=1, column=3, sticky=tk.W, padx=5, pady=5)
        
        # Remember password checkbox
        ttk.Checkbutton(conn_frame, text="Remember Password", variable=self.ssh_remember_password).grid(
            row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Connect/Disconnect buttons
        button_frame = ttk.Frame(conn_frame)
        button_frame.grid(row=3, column=0, columnspan=4, sticky=tk.W, pady=5)
        
        self.ssh_connect_button = ttk.Button(button_frame, text="Connect", command=self.ssh_connect)
        self.ssh_connect_button.pack(side=tk.LEFT, padx=5)
        
        self.ssh_disconnect_button = ttk.Button(button_frame, text="Disconnect", command=self.ssh_disconnect, state=tk.DISABLED)
        self.ssh_disconnect_button.pack(side=tk.LEFT, padx=5)
        
        # Current directory display
        path_frame = ttk.Frame(ssh_frame)
        path_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(path_frame, text="Current Directory:").pack(side=tk.LEFT, padx=5)
        
        # Create a custom Entry widget for current directory that will work with dark mode
        self.ssh_current_dir_entry = tk.Entry(path_frame, textvariable=self.ssh_current_dir, width=50, state="readonly")
        self.ssh_current_dir_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Apply the current theme immediately
        if self.is_dark_mode.get():
            self.ssh_current_dir_entry.config(readonlybackground='#3E3E3E', fg='#FFFFFF')
        else:
            self.ssh_current_dir_entry.config(readonlybackground='#F0F0F0', fg='#000000')
        
        # Main browser area with fixed height
        browser_frame = ttk.LabelFrame(ssh_frame, text="Remote Files", height=400)
        browser_frame.pack(fill=tk.BOTH, expand=True)
        browser_frame.pack_propagate(False)  # Prevent the frame from resizing to its contents
        
        # File listbox and navigation buttons
        files_frame = ttk.Frame(browser_frame, padding=5)
        files_frame.pack(fill=tk.BOTH, expand=True)
        
        # Navigation and action buttons at top
        nav_frame = ttk.Frame(files_frame)
        nav_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(nav_frame, text="Parent Directory", command=self.go_to_parent_dir).pack(side=tk.LEFT, padx=5)
        ttk.Button(nav_frame, text="Refresh", command=self.refresh_remote_files).pack(side=tk.LEFT, padx=5)
        
        # Download button with accent style
        self.ssh_download_button = ttk.Button(
            nav_frame, 
            text="Download Selected File", 
            command=self.download_selected_files,
            style="Accent.TButton"
        )
        self.ssh_download_button.pack(side=tk.RIGHT, padx=5)
        
        # File listbox with scrollbar
        list_frame = ttk.Frame(files_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.remote_listbox = tk.Listbox(list_frame, height=15, yscrollcommand=scrollbar.set)
        self.remote_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.remote_listbox.bind("<Double-Button-1>", self.on_remote_file_doubleclick)
        scrollbar.config(command=self.remote_listbox.yview)
        
        # Set listbox colors based on theme
        if self.is_dark_mode.get():
            self.remote_listbox.config(bg='#1E1E1E', fg='#CCCCCC', selectbackground='#4E4E4E', selectforeground='#FFFFFF')
        else:
            self.remote_listbox.config(bg='#FFFFFF', fg='#000000', selectbackground='#0078D7', selectforeground='#FFFFFF')
        
        # Initialize SSH client
        self.ssh_client = None
        self.sftp_client = None
        
        # Create hashes directory if it doesn't exist
        self.hashes_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hashes")
        os.makedirs(self.hashes_dir, exist_ok=True)
        
        # Bind session combo event
        self.session_combo.bind("<<ComboboxSelected>>", self.on_session_selected)
    
    def save_ssh_session(self):
        """Save the current SSH connection settings as a session"""
        # First check if we have a session name
        session_name = self.ssh_session_name.get().strip()
        if not session_name:
            # Ask for a session name
            session_name = tk.simpledialog.askstring("Session Name", 
                                                     "Enter a name for this session:",
                                                     parent=self.ssh_tab)
            if not session_name:  # User cancelled
                return
            
            self.ssh_session_name.set(session_name)
        
        # Get the session data
        session_data = {
            "host": self.ssh_host.get(),
            "port": self.ssh_port.get(),
            "username": self.ssh_username.get(),
            "password": self.ssh_password.get() if self.ssh_remember_password.get() else "",
            "remember_password": self.ssh_remember_password.get()
        }
        
        # Load existing sessions
        sessions = self.load_ssh_sessions_data()
        
        # Add or update this session
        sessions[session_name] = session_data
        
        # Save the sessions back to file
        try:
            # Ensure the SSH sessions file is defined
            if not hasattr(self, 'ssh_sessions_file'):
                config_dir = os.path.join(os.path.expanduser("~"), ".p4wnforge")
                os.makedirs(config_dir, exist_ok=True)
                self.ssh_sessions_file = os.path.join(config_dir, "ssh_sessions.json")
                
            with open(self.ssh_sessions_file, 'w') as f:
                json.dump(sessions, f)
            
            self.log_output(f"Session '{session_name}' saved successfully.")
            
            # Update the combobox
            self.update_session_combobox(session_name)
        except Exception as e:
            error_msg = f"Error saving session: {str(e)}"
            self.log_output(error_msg)
            messagebox.showerror("Error", error_msg)
            
    def load_ssh_sessions(self):
        """Load available SSH sessions into the combobox"""
        sessions = self.load_ssh_sessions_data()
        
        # Update combobox values
        session_names = list(sessions.keys())
        self.session_combo['values'] = session_names
        
        # If there are sessions and none is selected, select the first one
        if session_names and not self.ssh_session_name.get():
            self.session_combo.current(0)
    
    def load_ssh_sessions_data(self):
        """Load SSH sessions data from file"""
        try:
            # Ensure the SSH sessions file is defined
            if not hasattr(self, 'ssh_sessions_file'):
                config_dir = os.path.join(os.path.expanduser("~"), ".p4wnforge")
                os.makedirs(config_dir, exist_ok=True)
                self.ssh_sessions_file = os.path.join(config_dir, "ssh_sessions.json")
                
            if os.path.exists(self.ssh_sessions_file):
                with open(self.ssh_sessions_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.log_output(f"Error loading SSH sessions: {str(e)}")
        
        return {}  # Return empty dict if file doesn't exist or can't be read
    
    def update_session_combobox(self, selected_session=None):
        """Update the sessions combobox with current sessions"""
        sessions = self.load_ssh_sessions_data()
        session_names = list(sessions.keys())
        
        self.session_combo['values'] = session_names
        
        # Select the specified session or keep current selection
        if selected_session and selected_session in session_names:
            self.ssh_session_name.set(selected_session)
    
    def load_ssh_session(self):
        """Load the selected SSH session details"""
        session_name = self.ssh_session_name.get()
        if not session_name:
            messagebox.showinfo("Selection Required", "Please select a session to load")
            return
        
        sessions = self.load_ssh_sessions_data()
        if session_name in sessions:
            session = sessions[session_name]
            
            # Update the connection fields
            self.ssh_host.set(session.get("host", ""))
            self.ssh_port.set(session.get("port", "22"))
            self.ssh_username.set(session.get("username", ""))
            
            # Only set password if it was saved
            if session.get("remember_password", False):
                self.ssh_password.set(session.get("password", ""))
            else:
                self.ssh_password.set("")
            
            # Update the remember password checkbox
            self.ssh_remember_password.set(session.get("remember_password", False))
            
            self.log_output(f"Loaded SSH session: {session_name}")
        else:
            messagebox.showerror("Error", f"Session '{session_name}' not found")
    
    def delete_ssh_session(self):
        """Delete the selected SSH session"""
        session_name = self.ssh_session_name.get()
        if not session_name:
            messagebox.showinfo("Selection Required", "Please select a session to delete")
            return
        
        # Confirm deletion
        confirm = messagebox.askyesno("Confirm Delete", 
                                      f"Are you sure you want to delete the session '{session_name}'?",
                                      icon='warning')
        if not confirm:
            return
        
        # Load sessions
        sessions = self.load_ssh_sessions_data()
        
        # Remove the session
        if session_name in sessions:
            del sessions[session_name]
            
            # Save back to file
            try:
                # Ensure the SSH sessions file is defined
                if not hasattr(self, 'ssh_sessions_file'):
                    config_dir = os.path.join(os.path.expanduser("~"), ".p4wnforge")
                    os.makedirs(config_dir, exist_ok=True)
                    self.ssh_sessions_file = os.path.join(config_dir, "ssh_sessions.json")
                    
                with open(self.ssh_sessions_file, 'w') as f:
                    json.dump(sessions, f)
                
                self.log_output(f"Session '{session_name}' deleted.")
                
                # Update combobox and clear fields
                self.ssh_session_name.set("")
                self.update_session_combobox()
                
                # Clear connection fields
                self.ssh_host.set("")
                self.ssh_port.set("22")
                self.ssh_username.set("")
                self.ssh_password.set("")
            except Exception as e:
                error_msg = f"Error deleting session: {str(e)}"
                self.log_output(error_msg)
                messagebox.showerror("Error", error_msg)
    
    def on_session_selected(self, event=None):
        """Called when a session is selected in the combobox"""
        # Automatically load the selected session
        self.load_ssh_session()
        
    def ssh_connect(self):
        """Connect to SSH server"""
        host = self.ssh_host.get().strip()
        port = int(self.ssh_port.get().strip())
        username = self.ssh_username.get().strip()
        password = self.ssh_password.get()
        
        if not host or not username:
            messagebox.showerror("Error", "Host and username are required")
            return
        
        try:
            # Create SSH client
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect to server
            self.log_output(f"Connecting to {username}@{host}:{port}...")
            client.connect(host, port=port, username=username, password=password)
            self.log_output(f"Connected to {host}")
            
            # Open SFTP session
            sftp = client.open_sftp()
            
            # Store client and update UI
            self.ssh_client = client
            self.sftp_client = sftp
            self.ssh_current_dir.set("/")
            
            # Update button states
            self.ssh_connect_button.config(state=tk.DISABLED)
            self.ssh_disconnect_button.config(state=tk.NORMAL)
            
            # Load initial directory
            self.refresh_remote_files()
            
        except Exception as e:
            error_msg = f"SSH connection error: {str(e)}"
            self.log_output(error_msg)
            messagebox.showerror("Connection Error", error_msg)
    
    def ssh_disconnect(self):
        """Disconnect from SSH server"""
        if self.sftp_client:
            self.sftp_client.close()
            self.sftp_client = None
        
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None
            
        # Update UI
        self.remote_listbox.delete(0, tk.END)
        self.ssh_connect_button.config(state=tk.NORMAL)
        self.ssh_disconnect_button.config(state=tk.DISABLED)
        
        self.log_output("Disconnected from SSH server")
    
    def refresh_remote_files(self):
        """Refresh the remote files list"""
        if not self.sftp_client:
            return
        
        try:
            # Clear current list
            self.remote_listbox.delete(0, tk.END)
            
            # Get current directory
            current_dir = self.ssh_current_dir.get()
            
            # List files in current directory
            file_list = self.sftp_client.listdir(current_dir)
            
            # Add parent directory option if not at root
            if current_dir != "/":
                self.remote_listbox.insert(tk.END, "../")
            
            # Add directories first
            for filename in sorted(file_list):
                path = self._join_remote_path(current_dir, filename)
                try:
                    attrs = self.sftp_client.stat(path)
                    if S_ISDIR(attrs.st_mode):
                        self.remote_listbox.insert(tk.END, f"{filename}/")
                except Exception:
                    # Skip if we can't stat the file
                    pass
            
            # Then add files
            for filename in sorted(file_list):
                path = self._join_remote_path(current_dir, filename)
                try:
                    attrs = self.sftp_client.stat(path)
                    if not S_ISDIR(attrs.st_mode):
                        self.remote_listbox.insert(tk.END, filename)
                except Exception:
                    # Skip if we can't stat the file
                    pass
            
        except Exception as e:
            error_msg = f"Error listing directory: {str(e)}"
            self.log_output(error_msg)
            messagebox.showerror("Error", error_msg)
    
    def on_remote_file_doubleclick(self, event):
        """Handle double-click on remote file list"""
        if not self.sftp_client:
            return
        
        selection = self.remote_listbox.curselection()
        if not selection:
            return
        
        selected_item = self.remote_listbox.get(selection[0])
        
        # Check if it's the parent directory
        if selected_item == "../":
            self.go_to_parent_dir()
            return
        
        # Check if it's a directory
        if selected_item.endswith("/"):
            new_dir = self._join_remote_path(self.ssh_current_dir.get(), selected_item.rstrip("/"))
            self.ssh_current_dir.set(new_dir)
            self.refresh_remote_files()
    
    def go_to_parent_dir(self):
        """Navigate to parent directory"""
        if not self.sftp_client:
            return
        
        current_dir = self.ssh_current_dir.get()
        if current_dir == "/":
            return  # Already at root
        
        # Get parent directory
        parent_dir = os.path.dirname(current_dir)
        if not parent_dir:
            parent_dir = "/"
        
        self.ssh_current_dir.set(parent_dir)
        self.refresh_remote_files()
    
    def download_selected_files(self):
        """Download selected files to a user-selected location"""
        if not self.sftp_client:
            return
        
        selection = self.remote_listbox.curselection()
        if not selection:
            messagebox.showinfo("Selection Required", "Please select a file to download")
            return
        
        selected_item = self.remote_listbox.get(selection[0])
        
        # Skip if it's the parent directory or a directory
        if selected_item == "../" or selected_item.endswith("/"):
            messagebox.showinfo("Info", "Cannot download directories. Please select a file.")
            return
        
        # Construct remote path
        remote_path = self._join_remote_path(self.ssh_current_dir.get(), selected_item)
        
        # Ask user for download location
        local_path = filedialog.asksaveasfilename(
            title="Save File As",
            initialfile=selected_item,
            defaultextension=""  # Prevent adding default extension
        )
        
        if not local_path:  # User cancelled
            return
        
        try:
            # Download file
            self.log_output(f"Downloading {remote_path} to {local_path}...")
            self.sftp_client.get(remote_path, local_path)
            self.log_output(f"Downloaded {selected_item} successfully")
            messagebox.showinfo("Success", f"Downloaded {selected_item} successfully")
        except Exception as e:
            error_msg = f"Error downloading file: {str(e)}"
            self.log_output(error_msg)
            messagebox.showerror("Error", error_msg)
    
    def _join_remote_path(self, path, filename):
        """Join remote path components correctly"""
        if path.endswith("/"):
            return path + filename
        else:
            return path + "/" + filename

    def send_status_command(self):
        """Send the 's' status command to the running hashcat process"""
        if self.is_cracking and self.cracking_process and self.cracking_process.poll() is None:
            try:
                self.log_output("Sending status command to hashcat...")
                self.cracking_process.stdin.write('s\n')
                self.cracking_process.stdin.flush()
                self.log_output("Status command sent successfully.")
            except Exception as e:
                self.log_output(f"Error sending status command: {str(e)}")
                if "not writable" in str(e):
                    self.log_output("Status command is only available in bruteforce mode.")
        else:
            self.log_output("No active cracking process to send status command to.")

    def find_default_dictionaries(self):
        """Find dictionaries in common locations"""
        # Get our standard dictionary directory first
        dict_dir = self._get_dictionary_directory()
        if dict_dir and os.path.exists(dict_dir):
            common_paths = [dict_dir]
        else:
            common_paths = []
            
        # Add other default dictionary paths
        app_dict_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dictionaries")
        if app_dict_dir not in common_paths:
            common_paths.insert(0, app_dict_dir)  # Prioritize app dictionary directory
            
        common_paths.extend([
            os.path.expanduser("~/wordlists"),
            os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'hashcat', 'wordlists')
        ])
        
        found_dicts = []
        # Try to find dictionary files in common locations
        for path in common_paths:
            if os.path.exists(path):
                for file in os.listdir(path):
                    if file.endswith('.txt') or file.endswith('.dict'):
                        dict_path = os.path.join(path, file)
                        found_dicts.append(dict_path)
                        if dict_path not in self.dictionary_files:
                            self.dictionary_files.append(dict_path)
        
        # Add found dictionaries to the list
        for dict_path in found_dicts:
            if hasattr(self, 'dict_listbox'):
                self.dict_listbox.insert(tk.END, dict_path)
        
        # Save the found dictionaries
        self.save_dictionaries()

    def _get_password_from_potfile(self, hash_file, hash_type):
        """Get the password from the potfile by running hashcat with --show"""
        try:
            # First check if there's a cracked_password.txt file
            outfile_path = hash_file.replace("_processed.txt", "_cracked.txt")
            if os.path.exists(outfile_path):
                with open(outfile_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().strip()
                    if content:
                        # For NetNTLMv2, the password is at the end after the last colon
                        if hash_type in ["NetNTLMv2", "NTLMv2"] and ":" in content:
                            password = content.split(":")[-1].strip()
                            self.log_output(f"PASSWORD FOUND: {password}", is_password=True)
                            self._save_cracked_password(hash_file, password)
                            # Show success message box
                            messagebox.showinfo("Success!", f"Password found: {password}")
                            return True
            
            # If no cracked_password.txt or couldn't parse it, try running hashcat --show
            hash_mode = "5600" if hash_type in ["NetNTLMv2", "NTLMv2"] else "1000"
            command = [self.hashcat_path, "-m", hash_mode, "--show", hash_file]
            self.log_output(f"Running command to get password: {' '.join(command)}")
            
            show_result = subprocess.run(command, capture_output=True, text=True)
            output = show_result.stdout.strip()
            
            if output:
                # For NetNTLMv2, the password is at the end after the last colon
                if hash_type in ["NetNTLMv2", "NTLMv2"] and ":" in output:
                    password = output.split(":")[-1].strip()
                    self.log_output(f"PASSWORD FOUND: {password}", is_password=True)
                    self._save_cracked_password(hash_file, password)
                    # Show success message box
                    messagebox.showinfo("Success!", f"Password found: {password}")
                    return True
                # For regular NTLM, try to extract password
                elif ":" in output:
                    password = output.split(":", 1)[1].strip()
                    self.log_output(f"PASSWORD FOUND: {password}", is_password=True)
                    self._save_cracked_password(hash_file, password)
                    # Show success message box
                    messagebox.showinfo("Success!", f"Password found: {password}")
                    return True
            
            self.log_output("Could not retrieve password from potfile.", is_password=True)
            return False
        except Exception as e:
            self.log_output(f"Error getting password from potfile: {str(e)}")
            return False

def create_splash_screen(root):
    """Create and show a splash screen"""
    splash = tk.Toplevel(root)
    splash.title("P4wnForge")
    splash.overrideredirect(True)  # Remove window decorations
    
    # Calculate position to center the splash screen
    splash_width = 400
    splash_height = 400
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x_position = (screen_width - splash_width) // 2
    y_position = (screen_height - splash_height) // 2
    
    splash.geometry(f"{splash_width}x{splash_height}+{x_position}+{y_position}")
    
    try:
        # Load the splash image
        splash_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "p4wnForgeSplash.webp")
        if os.path.exists(splash_path):
            img = Image.open(splash_path)
            img = img.resize((splash_width, splash_height), Image.LANCZOS)
            splash_img = ImageTk.PhotoImage(img)
            
            # Create a label with the image
            splash_label = tk.Label(splash, image=splash_img)
            splash_label.image = splash_img  # Keep a reference
            splash_label.pack(fill="both", expand=True)
        else:
            # Fallback if image not found
            tk.Label(splash, text="P4wnForge", font=("Helvetica", 24, "bold")).pack(pady=50)
    except Exception as e:
        print(f"Error creating splash screen: {e}")
        # Fallback if there's an error
        tk.Label(splash, text="P4wnForge", font=("Helvetica", 24, "bold")).pack(pady=50)
    
    # Make sure splash is on top and gets focus
    splash.attributes('-topmost', True)
    splash.update()
    
    return splash

def main():
    root = tk.Tk()
    root.withdraw()  # Hide the main window initially
    
    # Show splash screen
    splash = create_splash_screen(root)
    
    # Function to destroy splash and show main window
    def close_splash():
        splash.destroy()
        root.deiconify()  # Show the main window
        app = PasswordCrackerApp(root)
    
    # Schedule the splash to close after 2 seconds
    root.after(2000, close_splash)
    
    root.mainloop()

if __name__ == "__main__":
    main()
