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

# Ensure you have installed PyMuPDF (pip install PyMuPDF)
import fitz  # PyMuPDF

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
        self.root.title("PassCrack Password Recovery Tool")
        self.root.geometry("950x700")
        self.root.minsize(800, 600)
        
        # Set application icon
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hightech.png")
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
            'sash_position': 400
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
        self.main_paned.add(self.tab_control, weight=2)  # Give more weight to top panel
        
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
        self.main_paned.add(self.lower_frame, weight=1)  # Give less weight to bottom panel
        
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
        self.output_text.insert(tk.END, "PassCrack initialized - ready to recover passwords\n")
        
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
                    # Schedule the sash position setting after a short delay
                    # This ensures the window is fully rendered before setting the position
                    self.root.after(100, lambda: self.main_paned.sashpos(0, self.config['sash_position']))
                else:
                    # Default to 70% of height for tabs, 30% for output
                    height = self.root.winfo_height()
                    try:
                        # Schedule with a delay for the same reason
                        self.root.after(100, lambda: self.main_paned.sashpos(0, int(height * 0.7)))
                    except Exception as e:
                        print(f"Error setting default sash position: {e}")
            except Exception as e:
                print(f"Error setting sash position: {e}")

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
            config_dir = os.path.join(os.path.expanduser("~"), ".passcrack")
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
            import traceback
            traceback.print_exc()
            # Use default values from config
            self.root.geometry(f"{self.config['window_width']}x{self.config['window_height']}")

    def save_window_config(self):
        """Save window configuration to file"""
        try:
            # Ensure config file path is defined
            if not hasattr(self, 'config_file'):
                config_dir = os.path.join(os.path.expanduser("~"), ".passcrack")
                os.makedirs(config_dir, exist_ok=True)
                self.config_file = os.path.join(config_dir, "config.json")
            
            # Update config with current window state
            geometry = self.root.geometry().replace('x', '+').split('+')
            if len(geometry) >= 3:
                self.config['window_width'] = int(geometry[0])
                self.config['window_height'] = int(geometry[1])
                self.config['window_x'] = int(geometry[2])
                self.config['window_y'] = int(geometry[3]) if len(geometry) > 3 else 0
            
            # Save sash position if main_paned exists
            if hasattr(self, 'main_paned'):
                try:
                    # Only save if sash position is reasonable (not collapsed)
                    sash_pos = self.main_paned.sashpos(0)
                    if sash_pos > 100:  # Ensure we're not saving a fully collapsed position
                        self.config['sash_position'] = sash_pos
                except Exception as e:
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
                               indicatorsize=14)  # Larger indicator for better visibility
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
                          indicatorcolor=[('selected', '#0078D7'), ('', '#E0E0E0')])  # Blue when selected
            
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
    
    def load_dictionary_list(self):
        """Load the list of dictionaries and scan default locations"""
        # First, ensure the dictionaries file is defined
        if not hasattr(self, 'dictionaries_file'):
            config_dir = os.path.join(os.path.expanduser("~"), ".passcrack")
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
                config_dir = os.path.join(os.path.expanduser("~"), ".passcrack")
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
                config_dir = os.path.join(os.path.expanduser("~"), ".passcrack")
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
            dict_dir = os.path.join(os.path.expanduser("~"), ".passcrack", "dictionaries")
            os.makedirs(dict_dir, exist_ok=True)
            
            if os.access(dict_dir, os.W_OK):
                return dict_dir
                
            # Try Documents folder if home directory isn't writable
            documents_dir = os.path.join(os.path.expanduser("~"), "Documents")
            dict_dir = os.path.join(documents_dir, "PassCrack_Dictionaries")
            os.makedirs(dict_dir, exist_ok=True)
            
            if os.access(dict_dir, os.W_OK):
                return dict_dir
                
            # Try Temp directory as final fallback
            dict_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "PassCrack_Dictionaries")
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
        
        # If we're using bruteforce, prompt for password length
        if is_bruteforce:
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
        if self.cracking_process and self.cracking_process.poll() is None:
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
                else:
                    self.log_output("Password not found or could not parse output.", is_password=True)
        except Exception as e:
            self.log_output(f"Error executing hashcat command: {str(e)}")
            self.log_output("Command that failed: " + " ".join(command))
    
    def _crack_pdf(self):
        # PDF cracking method using pdf2john and hashcat
        pdf_path = self.target_file_path.get().strip()
        
        if not pdf_path:
            messagebox.showerror("Error", "Please select a PDF file to crack")
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
        
        # PDF hash mode for hashcat is 10500 (PDF 1.1-1.3) or 10600 (PDF 1.4-1.6)
        # Use 10700 as a more universal option that handles different PDF versions
        pdf_hash_mode = "10700"
        command = [self.hashcat_path if os.path.dirname(self.hashcat_path)
                   else ("hashcat.exe" if sys.platform=="win32" else "hashcat")]
        
        try:
            self.log_output("Extracting hash from PDF document...")
            pdf2john_path = self.find_extraction_tool("pdf2john.py")
            if pdf2john_path:
                self.log_output(f"Using pdf2john.py at {pdf2john_path} to extract hash...")
                extract_cmd = [sys.executable, pdf2john_path, pdf_path]
                result = subprocess.run(extract_cmd, capture_output=True, text=True)
                raw_output = result.stdout.strip()
                self.log_output(f"Raw hash output: {raw_output[:50]}...")
                
                # Save the hash
                with open(hash_file, 'w') as f:
                    f.write(raw_output)
                self.log_output(f"Hash extracted to {hash_file}")
                
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
                    
                    command.extend(["-m", pdf_hash_mode, "-a", "3", hash_file, mask, "--increment"])
                    self.log_output(f"Using bruteforce with mask: {mask} (max length: {max_length}, character sets: {', '.join(char_sets)})", "info")
                    
                    # Add optimizations for bruteforce
                    command.extend(["--workload-profile", "3"])  # Better performance
                    command.extend(["--optimized-kernel-enable"])
                    
                    # For bruteforce, use stdin pipe for possible interactive use
                    use_pipe = True
                    self.log_output("Note: This may take a long time for complex passwords!", "warning")
                else:
                    # Use dictionary attack (attack mode 0)
                    wordlist_path = self.password_list_path.get().strip()
                    if not wordlist_path:
                        messagebox.showerror("Error", "Please select a wordlist file for dictionary attack")
                        return
                    
                    command.extend(["-m", pdf_hash_mode, "-a", "0", hash_file, wordlist_path])
                    use_pipe = False
                
                # Redirect output to a file in the same directory as the hash
                outfile_path = os.path.join(pdf_hashes_dir, f"{os.path.splitext(target_filename)[0]}_cracked.txt").replace('\\', '/')
                command.extend(["--outfile", outfile_path])
                if "--force" not in command:
                    command.append("--force")
                
                self.log_output(f"Executing command: {' '.join(command)}")
                hashcat_dir = os.path.dirname(self.hashcat_path) if os.path.dirname(self.hashcat_path) else None
                
                try:
                    if use_pipe:
                        self.cracking_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                                                stdin=subprocess.PIPE, text=True, bufsize=1, cwd=hashcat_dir)
                    else:
                        self.cracking_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                                                text=True, bufsize=1, cwd=hashcat_dir)
                    
                    for line in iter(self.cracking_process.stdout.readline, ''):
                        if not self.is_cracking:  # If process was stopped by user
                            break
                        self.log_output(line.strip())
                    
                    if self.is_cracking:  # Only process output if we haven't been manually stopped
                        self.cracking_process.wait()
                        # Run --show command to retrieve the password
                        show_cmd = [self.hashcat_path, "-m", pdf_hash_mode, "--show", hash_file]
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
                        else:
                            self.log_output("Password not found or could not parse output.", is_password=True)
                    return
                except Exception as e:
                    self.log_output(f"Error executing hashcat command: {str(e)}")
                    self.log_output("Command that failed: " + " ".join(command))
            except Exception as e:
                self.log_output(f"Error in PDF hash extraction: {str(e)}")
                messagebox.showerror("Error", f"An error occurred during PDF hash extraction: {str(e)}")
        else:
            self.log_output("pdf2john.py not found. Cannot extract hash.", "error")
            messagebox.showerror("Error", "pdf2john.py tool is required but not found")
            return
    
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
        
        # Check if using bruteforce mode
        is_bruteforce = self.hash_attack_type.get() == "Bruteforce" if hasattr(self, 'hash_attack_type') else False
        
        # Copy or prepare the hash file
        if os.path.exists(target_file):
            # Copy the hash file to our hashes directory
            with open(target_file, 'r') as src_file:
                hash_content = src_file.read().strip()
            
            with open(hash_file, 'w') as dest_file:
                dest_file.write(hash_content)
            
            self.log_output(f"Hash file copied to {hash_file}")
        else:
            # If target_file doesn't exist, it might be direct hash input
            hash_content = target_file.strip()
            with open(hash_file, 'w') as f:
                f.write(hash_content)
            self.log_output(f"Hash saved to {hash_file}")
        
        # Determine the hash type - default to NTLM (1000)
        hash_mode = "1000"  # Default to NTLM
        
        # Set up the hashcat command
        command = [self.hashcat_path if os.path.dirname(self.hashcat_path)
                   else ("hashcat.exe" if sys.platform=="win32" else "hashcat")]
        
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
            
            command.extend(["-m", hash_mode, "-a", "3", hash_file, mask, "--increment"])
            self.log_output(f"Using bruteforce with mask: {mask} (max length: {max_length}, character sets: {', '.join(char_sets)})", "info")
        else:
            # Use dictionary attack (attack mode 0)
            command.extend(["-m", hash_mode, "-a", "0", hash_file, self.password_list_path.get()])
            use_pipe = False
        
        # Set output file in the hashes directory
        outfile_path = os.path.join(ntlm_hashes_dir, f"{os.path.splitext(target_filename)[0]}_cracked.txt").replace('\\', '/')
        command.extend(["--outfile", outfile_path])
        
        if "--force" not in command:
            command.append("--force")
            
        self.log_output(f"Executing command: {' '.join(command)}")
        hashcat_dir = os.path.dirname(self.hashcat_path) if os.path.dirname(self.hashcat_path) else None
        
        try:
            if use_pipe:
                self.cracking_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                                       stdin=subprocess.PIPE, text=True, bufsize=1, cwd=hashcat_dir)
            else:
                self.cracking_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                                       text=True, bufsize=1, cwd=hashcat_dir)
                
            for line in iter(self.cracking_process.stdout.readline, ''):
                if not self.is_cracking:  # If process was stopped by user
                    break
                self.log_output(line.strip())
            
            if self.is_cracking:  # Only show completion message if not manually stopped
                self.cracking_process.wait()
                
                # Run --show command to retrieve the password
                show_cmd = [self.hashcat_path, "-m", hash_mode, "--show", hash_file]
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
                else:
                    self.log_output("Password not found or could not parse output.", is_password=True)
        except Exception as e:
            self.log_output(f"Error executing hashcat command: {str(e)}")
            self.log_output("Command that failed: " + " ".join(command))
    
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
            default_filename = f"passcrack_output_{timestamp}.txt"
            
            # Get output directory path
            output_dir = os.path.join(os.path.expanduser("~"), ".passcrack", "logs")
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
        ttk.Entry(path_frame, textvariable=self.ssh_current_dir, width=50, state="readonly").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
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
                config_dir = os.path.join(os.path.expanduser("~"), ".passcrack")
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
                config_dir = os.path.join(os.path.expanduser("~"), ".passcrack")
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
                    config_dir = os.path.join(os.path.expanduser("~"), ".passcrack")
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

def main():
    root = tk.Tk()
    app = PasswordCrackerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
