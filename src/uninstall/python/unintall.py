import os
import shutil
import subprocess
import sys
import ctypes
import winreg
from tkinter import messagebox
import customtkinter as ctk
from PIL import Image

# ========== Constants & Setup ==========
APP_NAME = "BlockManager Uninstaller"
THEME_COLOR = "#2b5dff"  # Modern blue accent

# ========== Admin Check ==========
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

if not is_admin():
    run_as_admin()

# ========== GUI Setup ==========
ctk.set_appearance_mode("System")  # Auto light/dark
ctk.set_default_color_theme("blue")

class UninstallerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title(APP_NAME)
        self.geometry("600x450")
        self.minsize(500, 400)
        
        # Load icons (using emoji as fallback)
        self.trash_icon = self.load_icon("🗑️", size=(24, 24))
        self.warning_icon = self.load_icon("⚠️", size=(24, 24))
        self.success_icon = self.load_icon("✅", size=(24, 24))
        
        self.setup_ui()
    
    def load_icon(self, emoji_fallback, size=None):
        try:
            return ctk.CTkImage(Image.open("trash_icon.png"), size=size)  # Replace with your icon
        except:
            return emoji_fallback  # Fallback to emoji
    
    def setup_ui(self):
        # Main Frame
        self.main_frame = ctk.CTkFrame(self, corner_radius=10)
        self.main_frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        # Header
        self.header = ctk.CTkLabel(
            self.main_frame,
            text=APP_NAME,
            font=("Segoe UI", 20, "bold"),
            text_color=THEME_COLOR
        )
        self.header.pack(pady=(20, 10))
        
        # Description
        self.desc = ctk.CTkLabel(
            self.main_frame,
            text="This will remove BlockManager and all its components from your system.",
            font=("Segoe UI", 12),
            wraplength=400,
            justify="center"
        )
        self.desc.pack(pady=(0, 20))
        
        # Delete Configs Checkbox
        self.delete_configs_var = ctk.BooleanVar()
        self.delete_configs = ctk.CTkCheckBox(
            self.main_frame,
            text="Delete all configurations (including user settings)",
            variable=self.delete_configs_var,
            font=("Segoe UI", 12),
            checkbox_width=18,
            checkbox_height=18
        )
        self.delete_configs.pack(pady=10)
        
        # Uninstall Button
        self.uninstall_btn = ctk.CTkButton(
            self.main_frame,
            text="Uninstall Now",
            command=self.start_uninstall,
            fg_color=THEME_COLOR,
            hover_color="#1a4acc",
            font=("Segoe UI", 14, "bold"),
            height=40,
            corner_radius=8
        )
        self.uninstall_btn.pack(pady=20, ipadx=20)
        
        # Progress Bar (hidden initially)
        self.progress = ctk.CTkProgressBar(self.main_frame, mode="indeterminate")
        self.progress.set(0)
        
        # Log Textbox (hidden initially)
        self.log_text = ctk.CTkTextbox(self.main_frame, height=100, state="disabled")
        
    def start_uninstall(self):
        self.uninstall_btn.configure(state="disabled")
        self.progress.pack(pady=10, fill="x", padx=20)
        self.progress.start()
        
        self.log_text.pack(pady=10, fill="both", padx=20, expand=True)
        self.log_text.configure(state="normal")
        self.log_text.insert("end", "Starting uninstallation...\n")
        self.log_text.configure(state="disabled")
        
        self.after(100, self.run_uninstall)  # Run in background
        
    def run_uninstall(self):
        try:
            self.uninstall()
            self.progress.stop()
            self.progress.pack_forget()
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            self.progress.stop()
            self.uninstall_btn.configure(state="normal")
            messagebox.showerror(
                "Error",
                f"Uninstallation failed:\n{str(e)}",
                parent=self
            )
    
    def log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.update()
    
    def get_all_user_profiles(self):
        user_profiles = []
        try:
            reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList")
            i = 0
            while True:
                try:
                    sid = winreg.EnumKey(reg_key, i)
                    profile_path = winreg.QueryValueEx(winreg.OpenKey(reg_key, sid), "ProfileImagePath")[0]
                    user_profiles.append(profile_path)
                    i += 1
                except WindowsError:
                    break
        except Exception as e:
            self.log(f"⚠️ Failed to fetch user profiles: {e}")
        return user_profiles
    
    def uninstall(self):
        program_files = os.environ.get("ProgramFiles")
        self.log("🔍 Searching for BlockManager files...")
        
        # Files to delete
        targets = [
            os.path.join(program_files, "BlockManager", "blocker.exe"),
            os.path.join(program_files, "BlockManager", "BlockManager.exe"),
            os.path.join(program_files, "BlockManager", "notification.exe"),
            os.path.join(program_files, "BlockManager", "server_response.exe"),
            os.path.join(program_files, "BlockManager", "updater.exe"),
            os.path.join(program_files, "BlockManager", "logs")
        ]
        
        # Delete main files
        for target in targets:
            try:
                if os.path.exists(target):
                    if os.path.isfile(target):
                        os.remove(target)
                        self.log(f"🗑️ Deleted: {target}")
                    elif os.path.isdir(target):
                        shutil.rmtree(target)
                        self.log(f"🗑️ Deleted folder: {target}")
            except Exception as e:
                self.log(f"⚠️ Failed to delete {target}: {e}")
        
        # Delete configs if selected
        if self.delete_configs_var.get():
            self.log("\n⚙️ Deleting configurations...")
            
            # Program Files configs
            configs = [
                os.path.join(program_files, "BlockManager", "config.json"),
                os.path.join(program_files, "BlockManager", "local.json")
            ]
            
            for config in configs:
                try:
                    if os.path.exists(config):
                        os.remove(config)
                        self.log(f"🗑️ Deleted config: {config}")
                except Exception as e:
                    self.log(f"⚠️ Failed to delete config {config}: {e}")
            
            # AppData for all users
            user_profiles = self.get_all_user_profiles()
            self.log(f"Пользователи: {user_profiles}")
            for profile in user_profiles:
                roaming_path = os.path.join(profile, "AppData", "Roaming", "BlockManager")
                try:
                    if os.path.exists(roaming_path):
                        shutil.rmtree(roaming_path)
                        self.log(f"🗑️ Deleted user data: {roaming_path}")
                except Exception as e:
                    self.log(f"⚠️ Failed to delete user data {roaming_path}: {e}")
        
        # Delete services
        self.log("\n🔧 Removing services...")
        services = ["BlockManagerService", "BlockManagerChecker", "BlockManagerUpdater"]
        for service in services:
            try:
                subprocess.run(["sc", "stop", service], check=True, capture_output=True)
                subprocess.run(["sc", "delete", service], check=True, capture_output=True)
                self.log(f"✅ Removed service: {service}")
            except subprocess.CalledProcessError as e:
                self.log(f"⚠️ Failed to remove service {service}: {e.stderr.decode().strip()}")
        
        # Delete empty folder
        block_manager_dir = os.path.join(program_files, "BlockManager")
        try:
            if os.path.exists(block_manager_dir) and not os.listdir(block_manager_dir):
                os.rmdir(block_manager_dir)
                self.log(f"✅ Removed empty folder: {block_manager_dir}")
        except Exception as e:
            self.log(f"⚠️ Could not remove folder {block_manager_dir}: {e}")
        
        self.log("\n🎉 Uninstallation complete!")

# ========== Run App ==========
if __name__ == "__main__":
    app = UninstallerApp()
    app.mainloop()