import customtkinter as ctk
import threading
import os
import json
import subprocess
from tkinter import messagebox
try:
    from PIL import Image
except ImportError:
    Image = None

from main import KliperrGenerator
from dotenv import load_dotenv, set_key

# Setup Theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green") 

# Constants
CONFIG_FILE = "config.json"
OUT_DIR = "hasil_shorts"
DEFAULT_SETTINGS = {
    "num_clips": 5,
    "duration_min": 30,
    "duration_max": 60,
    "font_size": 24, 
    "font_color": "#FFD700",
    "font_pos_y": 0.75,
    "font_family": "Arial-Bold"
}

# --- STYLES ---
COLOR_BG = "#0D1117"     # Very dark background (Github Dark Dimmed inspired)
COLOR_ACCENT = "#00E676" # Bright Green
COLOR_SURFACE = "#1A1A1A" # Slightly lighter for cards
COLOR_TEXT_MAIN = "white"
COLOR_TEXT_DIM = "#888888"

class GalleryFrame(ctk.CTkFrame):
    def __init__(self, master, app_instance):
        super().__init__(master, fg_color="transparent")
        self.app = app_instance
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=50)
        self.header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        
        self.back_btn = ctk.CTkButton(self.header, text="<", width=40, command=self.app.show_dashboard,
                                      fg_color="transparent", hover_color="#2B2B2B", font=("Arial", 20))
        self.back_btn.pack(side="left")
        
        self.title_label = ctk.CTkLabel(self.header, text="Kliperr Gallery", font=("Arial", 20, "bold"))
        self.title_label.pack(side="left", padx=80) 

        self.refresh_btn = ctk.CTkButton(self.header, text="↻", width=40, command=self.refresh_list,
                                         fg_color="transparent", hover_color="#2B2B2B", font=("Arial", 20))
        self.refresh_btn.pack(side="right")

        # Tabs (Visual only for now)
        self.tabs_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tabs_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        ctk.CTkButton(self.tabs_frame, text="Recent", fg_color="transparent", text_color=COLOR_ACCENT, 
                      border_width=0, font=("Arial", 14, "bold"), hover=False).pack(side="left", padx=10)
        ctk.CTkButton(self.tabs_frame, text="Saved", fg_color="transparent", text_color="gray", 
                      font=("Arial", 13, "bold"), hover=False).pack(side="left", padx=10)

        # Scrollable List
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=0)

        # Footer Button
        self.open_folder_btn = ctk.CTkButton(self, text="📂 Open Output Folder", height=50, 
                                             fg_color=COLOR_ACCENT, text_color="black", hover_color="#00C853",
                                             font=("Arial", 16, "bold"), command=self.open_output_folder)
        self.open_folder_btn.grid(row=3, column=0, sticky="ew", padx=20, pady=20)

        self.refresh_list()

    def refresh_list(self):
        # Clear existing
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        if not os.path.exists(OUT_DIR):
            ctk.CTkLabel(self.scroll_frame, text="No clips generated yet.", text_color="gray").pack(pady=20)
            return

        files = [f for f in os.listdir(OUT_DIR) if f.endswith(".mp4")]
        if not files:
            ctk.CTkLabel(self.scroll_frame, text="Folder is empty.", text_color="gray").pack(pady=20)
            return

        for f in files:
            self.create_video_card(f)

    def create_video_card(self, filename):
        card = ctk.CTkFrame(self.scroll_frame, fg_color=COLOR_SURFACE, corner_radius=10)
        card.pack(fill="x", padx=10, pady=5)

        # Icon / Thumbnail placeholder
        icon_frame = ctk.CTkFrame(card, width=50, height=70, fg_color="#333333", corner_radius=5)
        icon_frame.pack(side="left", padx=10, pady=10)
        ctk.CTkLabel(icon_frame, text="▶", font=("Arial", 14)).place(relx=0.5, rely=0.5, anchor="center")

        # Info
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, pady=10)
        
        ctk.CTkLabel(info_frame, text=filename[:25]+"...", font=("Arial", 14, "bold"), anchor="w", text_color="white").pack(fill="x")
        ctk.CTkLabel(info_frame, text="1080x1920 • YouTube Source", font=("Arial", 11), text_color="gray", anchor="w").pack(fill="x")

        # Play Button
        play_btn = ctk.CTkButton(card, text="▶", width=40, height=40, corner_radius=20,
                                 fg_color="#333333", hover_color=COLOR_ACCENT, text_color="white",
                                 command=lambda f=filename: self.play_video(f))
        play_btn.pack(side="right", padx=15)

    def play_video(self, filename):
        path = os.path.abspath(os.path.join(OUT_DIR, filename))
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open file: {e}")

    def open_output_folder(self):
        path = os.path.abspath(OUT_DIR)
        if not os.path.exists(path): os.makedirs(path)
        os.startfile(path)


class SettingsFrame(ctk.CTkFrame):
    def __init__(self, master, app_instance):
        super().__init__(master, fg_color="transparent")
        self.app = app_instance
        self.grid_columnconfigure(0, weight=1)
        self.settings = self.load_settings()

        # Header
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=50)
        self.header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        
        self.back_btn = ctk.CTkButton(self.header, text="<", width=40, command=self.app.show_dashboard,
                                      fg_color="transparent", hover_color="#2B2B2B", font=("Arial", 20))
        self.back_btn.pack(side="left")
        
        self.title_label = ctk.CTkLabel(self.header, text="Settings", font=("Arial", 20, "bold"))
        self.title_label.pack(side="left", padx=100)

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.grid_rowconfigure(1, weight=1)

        # API Settings
        self.add_section_label("API SETTINGS")
        self.api_frame = self.create_container()
        
        ctk.CTkLabel(self.api_frame, text="Groq API Key", anchor="w", text_color="#DDDDDD").pack(fill="x", padx=15, pady=(15, 5))
        self.api_entry = ctk.CTkEntry(self.api_frame, placeholder_text="gsk_...", show="*", fg_color="#0D1117", border_color="#333333")
        self.api_entry.pack(fill="x", padx=15, pady=5)
        current_key = os.getenv("GROQ_API_KEY", "")
        if current_key: self.api_entry.insert(0, current_key)

        self.save_api_btn = ctk.CTkButton(self.api_frame, text="Save API Key", fg_color=COLOR_ACCENT, 
                                          text_color="black", hover_color="#00C853", command=self.save_api_key)
        self.save_api_btn.pack(fill="x", padx=15, pady=15)

        # Video Settings
        self.add_section_label("VIDEO SETTINGS")
        self.video_frame = self.create_container()

        self.clips_label = ctk.CTkLabel(self.video_frame, text=f"Number of Clips: {self.settings['num_clips']}", anchor="w", text_color="#DDDDDD")
        self.clips_label.pack(fill="x", padx=15, pady=(15,0))
        self.clips_slider = ctk.CTkSlider(self.video_frame, from_=1, to=10, number_of_steps=9, command=self.update_clips_label, button_color=COLOR_ACCENT, progress_color=COLOR_ACCENT)
        self.clips_slider.set(self.settings['num_clips'])
        self.clips_slider.pack(fill="x", padx=15, pady=10)

        self.dur_label = ctk.CTkLabel(self.video_frame, text=f"Clip Duration (Max): {self.settings['duration_max']}s", anchor="w", text_color="#DDDDDD")
        self.dur_label.pack(fill="x", padx=15, pady=(10,0))
        self.dur_slider = ctk.CTkSlider(self.video_frame, from_=15, to=90, number_of_steps=75, command=self.update_dur_label, button_color=COLOR_ACCENT, progress_color=COLOR_ACCENT)
        self.dur_slider.set(self.settings['duration_max'])
        self.dur_slider.pack(fill="x", padx=15, pady=10)

        # Style Settings
        self.add_section_label("STYLE & SUBTITLES")
        self.style_frame = self.create_container()

        ctk.CTkLabel(self.style_frame, text="Font Family", anchor="w", text_color="#DDDDDD").pack(fill="x", padx=15, pady=(15,5))
        self.font_combo = ctk.CTkComboBox(self.style_frame, values=["Arial-Bold", "Impact", "Roboto-Bold"], fg_color="#0D1117", border_color="#333333")
        self.font_combo.set(self.settings['font_family'])
        self.font_combo.pack(fill="x", padx=15, pady=5)

        self.size_label = ctk.CTkLabel(self.style_frame, text=f"Font Size: {self.settings['font_size']}px", anchor="w", text_color="#DDDDDD")
        self.size_label.pack(fill="x", padx=15, pady=(10,0))
        self.size_slider = ctk.CTkSlider(self.style_frame, from_=10, to=100, command=self.update_size_label, button_color=COLOR_ACCENT, progress_color=COLOR_ACCENT)
        self.size_slider.set(self.settings['font_size'])
        self.size_slider.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(self.style_frame, text="Subtitle Color", anchor="w", text_color="#DDDDDD").pack(fill="x", padx=15, pady=(10,5))
        self.color_var = ctk.StringVar(value=self.settings['font_color'])
        self.color_seg = ctk.CTkSegmentedButton(self.style_frame, values=["#FFD700", "White", "#00E676"], variable=self.color_var, selected_color=COLOR_ACCENT, selected_hover_color="#00C853", unselected_color="#0D1117")
        self.color_seg.pack(fill="x", padx=15, pady=10)

        # Footer
        self.save_all_btn = ctk.CTkButton(self.scroll_frame, text="Save All Changes", height=50, 
                                          fg_color=COLOR_ACCENT, text_color="black", hover_color="#00C853",
                                          font=("Arial", 16, "bold"), command=self.save_settings)
        self.save_all_btn.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(self.scroll_frame, text="Reset to Defaults", fg_color="transparent", text_color="gray", hover_color="#222222").pack(pady=5)

    def create_container(self):
        frame = ctk.CTkFrame(self.scroll_frame, fg_color=COLOR_SURFACE, corner_radius=10, border_color="#333333", border_width=1)
        frame.pack(fill="x", padx=10, pady=5)
        return frame

    def add_section_label(self, text):
        label = ctk.CTkLabel(self.scroll_frame, text=text, font=("Arial", 12, "bold"), text_color="#AAAAAA", anchor="w")
        label.pack(fill="x", padx=15, pady=(20, 5))

    def update_clips_label(self, value): self.clips_label.configure(text=f"Number of Clips: {int(value)}")
    def update_dur_label(self, value): self.dur_label.configure(text=f"Clip Duration (Max): {int(value)}s")
    def update_size_label(self, value): self.size_label.configure(text=f"Font Size: {int(value)}px")

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return {**DEFAULT_SETTINGS, **json.load(f)}
        return DEFAULT_SETTINGS

    def save_api_key(self):
        key = self.api_entry.get().strip()
        if not key:
            messagebox.showerror("Error", "API Key cannot be empty")
            return
        env_path = os.path.join(os.getcwd(), ".env")
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f: f.write("")
        set_key(env_path, "GROQ_API_KEY", key)
        self.app.api_key = key
        messagebox.showinfo("Success", "API Key Saved!")

    def save_settings(self):
        new_settings = {
            "num_clips": int(self.clips_slider.get()),
            "duration_max": int(self.dur_slider.get()),
            "font_size": int(self.size_slider.get()),
            "font_family": self.font_combo.get(),
            "font_color": self.color_var.get(),
            "font_pos_y": 0.75
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(new_settings, f, indent=4)
        self.app.config = new_settings
        messagebox.showinfo("Success", "Settings Saved!")


class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master, app_instance):
        super().__init__(master, fg_color="transparent")
        self.app = app_instance
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1) # Row 4 (Preview) should expand, not 3

        # Header
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        
        self.menu_btn = ctk.CTkButton(self.header_frame, text="☰", width=30, fg_color="transparent", 
                                      hover_color="#2B2B2B", font=("Arial", 20), command=self.open_menu)
        self.menu_btn.pack(side="left")
        
        self.logo_label = ctk.CTkLabel(self.header_frame, text="Kliperr", font=("Arial", 20, "bold"))
        self.logo_label.pack(side="left", padx=100)

        # Input
        self.url_label = ctk.CTkLabel(self, text="YouTube URL / Local File", anchor="w", font=("Arial", 14))
        self.url_label.grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")

        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        self.url_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Video Source (URL / File)...", height=50, 
                                      fg_color=COLOR_SURFACE, border_color="#333333")
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.browse_btn = ctk.CTkButton(self.input_frame, text="Browse", width=60, height=50, fg_color=COLOR_SURFACE, 
                                      hover_color="#333333", border_width=1, border_color="#333333", command=self.browse_file)
        self.browse_btn.pack(side="right", padx=(0, 5))

        self.load_btn = ctk.CTkButton(self.input_frame, text="Load", width=60, height=50, fg_color=COLOR_SURFACE, 
                                      hover_color="#333333", border_width=1, border_color="#333333", command=self.load_video_info)
        self.load_btn.pack(side="right")

        # Audio Input (Optional)
        self.audio_frame = ctk.CTkFrame(self, fg_color="transparent", height=50) # Explicit height
        self.audio_frame.grid(row=3, column=0, padx=20, pady=(0, 5), sticky="ew")
        self.audio_frame.grid_propagate(False) # Prevent shrinking
        
        self.audio_entry = ctk.CTkEntry(self.audio_frame, placeholder_text="Audio Source (Optional - .wav, .mp3)...", height=40, font=("Arial", 12), text_color="gray")
        self.audio_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.browse_audio_btn = ctk.CTkButton(self.audio_frame, text="Audio", width=60, height=40, fg_color=COLOR_SURFACE,
                                              hover_color="#333333", border_width=1, border_color="#333333", command=self.browse_audio)
        self.browse_audio_btn.pack(side="right")

        # Preview
        self.preview_frame = ctk.CTkFrame(self, height=220, fg_color=COLOR_SURFACE, corner_radius=15, border_color="#222222", border_width=1)
        self.preview_frame.grid(row=4, column=0, padx=20, pady=30, sticky="nsew")
        
        self.preview_icon = ctk.CTkLabel(self.preview_frame, text="▶", font=("Arial", 40))
        self.preview_icon.place(relx=0.5, rely=0.4, anchor="center")
        self.preview_text = ctk.CTkLabel(self.preview_frame, text="Video preview will appear here", text_color="gray")
        self.preview_text.place(relx=0.5, rely=0.6, anchor="center")

        # Action
        self.generate_btn = ctk.CTkButton(self, text="✨ Generate Shorts", height=60, 
                                          font=("Arial", 18, "bold"), fg_color=COLOR_ACCENT, text_color="black", hover_color="#00C853",
                                          command=self.start_generation)
        self.generate_btn.grid(row=5, column=0, padx=20, pady=10, sticky="ew")
        
        self.cancel_btn = ctk.CTkLabel(self, text="Cancel Process", text_color="gray", cursor="hand2")
        self.cancel_btn.grid(row=6, column=0, pady=5)
        self.cancel_btn.bind("<Button-1>", self.cancel_process)

        # Log
        self.log_label = ctk.CTkLabel(self, text="● LIVE LOG", text_color=COLOR_ACCENT, font=("Consolas", 12, "bold"), anchor="w")
        self.log_label.grid(row=7, column=0, padx=20, pady=(20, 5), sticky="w")
        
        self.log_box = ctk.CTkTextbox(self, height=180, fg_color="black", text_color=COLOR_ACCENT, font=("Consolas", 10), corner_radius=10, border_width=1, border_color="#333333")
        self.log_box.grid(row=8, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.log_box.configure(state="disabled")

        # Menu Overlay (Hidden by default)
        self.menu_frame = None

    def browse_file(self):
        file_path = ctk.filedialog.askopenfilename(filetypes=[("Video Files", "*.mp4 *.mkv *.mov *.avi")])
        if file_path:
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, file_path)
            self.load_video_info() # Auto preview if supported logic added later, or just to validate

    def load_video_info(self):
        url = self.url_entry.get().strip()
        if not url:
            self.log("URL kosong!", "error")
            return

        self.load_btn.configure(state="disabled", text="Loading...")
        self.preview_text.configure(text="Fetching metadata...")
        
        # Use a temporary generator instance just for fetching info
        temp_gen = KliperrGenerator(self.app.api_key, logger_callback=self.log)
        
        def _fetch():
            info = temp_gen.get_video_info(url)
            self.after(0, lambda: self._update_preview(info))

        threading.Thread(target=_fetch, daemon=True).start()

    def _update_preview(self, info):
        self.load_btn.configure(state="normal", text="Load")
        
        if not info:
            self.preview_text.configure(text="Failed to load video info.")
            return

        # Update text
        title = info['title']
        if len(title) > 50: title = title[:47] + "..."
        self.preview_text.configure(text=f"{title}\nDuration: {info['duration']}")
        self.preview_icon.place_forget() # Hide generic icon

        # Load Thumbnail
        if not info.get('thumbnail'):
            self.preview_text.configure(text=f"{title}\nDuration: {info['duration']}\n(Local File)")
            return

        try:
            import requests # Import here to avoid global dep if not installed
            from io import BytesIO
            
            response = requests.get(info['thumbnail'])
            img_data = response.content
            image = Image.open(BytesIO(img_data))
            
            # Resize to fit preview (keep aspect ratio)
            # Preview height 220, width ~360 (based on 400 window pad 20)
            target_h = 220
            ratio = image.width / image.height
            target_w = int(target_h * ratio)
            
            ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(target_w, target_h))
            
            self.thumbnail_label = ctk.CTkLabel(self.preview_frame, text="", image=ctk_image)
            self.thumbnail_label.place(relx=0.5, rely=0.5, anchor="center")
            
            self.log(f"Video Loaded: {info['title']}", "success")
            
        except Exception as e:
            self.log(f"Thumbnail error: {e}", "error")

    def dummy_load(self):
        self.load_video_info()

    def log(self, message, type="info"):
        self.app.log(message, type)

    def browse_audio(self):
        file_path = ctk.filedialog.askopenfilename(filetypes=[("Audio Files", "*.wav *.mp3 *.m4a *.aac")])
        if file_path:
            self.audio_entry.delete(0, "end")
            self.audio_entry.insert(0, file_path)

    def start_generation(self):
        url = self.url_entry.get().strip()
        if not url:
            self.log("URL tidak boleh kosong!", "error")
            return
            
        external_audio = self.audio_entry.get().strip()
        self.app.start_generation(url, self.generate_btn, external_audio)

    def cancel_process(self, event=None):
        self.app.cancel_process()

    def open_menu(self):
        # Create a simple menu overlay or toggle
        menu = ctk.CTkToplevel(self)
        menu.geometry("200x300")
        menu.title("Menu")
        menu.attributes("-topmost", True)
        
        ctk.CTkButton(menu, text="Settings", command=lambda: [self.app.show_settings(), menu.destroy()]).pack(fill="x", pady=5)
        ctk.CTkButton(menu, text="Gallery", command=lambda: [self.app.show_gallery(), menu.destroy()]).pack(fill="x", pady=5)


class KliperrApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Kliperr")
        self.geometry("400x800")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)

        load_dotenv()
        self.api_key = os.getenv("GROQ_API_KEY")
        self.config = self.load_initial_config()

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.dashboard_frame = DashboardFrame(self.container, self)
        self.settings_frame = SettingsFrame(self.container, self)
        self.gallery_frame = GalleryFrame(self.container, self)

        self.show_dashboard()
        self.generator = None

    def load_initial_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f: return {**DEFAULT_SETTINGS, **json.load(f)}
        return DEFAULT_SETTINGS

    def show_dashboard(self):
        self.settings_frame.pack_forget()
        self.gallery_frame.pack_forget()
        self.dashboard_frame.pack(fill="both", expand=True)

    def show_settings(self):
        self.dashboard_frame.pack_forget()
        self.gallery_frame.pack_forget()
        self.settings_frame.pack(fill="both", expand=True)

    def show_gallery(self):
        self.dashboard_frame.pack_forget()
        self.settings_frame.pack_forget()
        self.gallery_frame.refresh_list()
        self.gallery_frame.pack(fill="both", expand=True)

    def log(self, message, type="info"):
        box = self.dashboard_frame.log_box
        box.configure(state="normal")
        prefix = "[ERROR] " if type == "error" else "[PASS] " if type == "success" else ""
        box.insert("end", f"{prefix}{message}\n")
        box.see("end")
        box.configure(state="disabled")

    def start_generation(self, url, btn_ref, external_audio=None):
        if not self.api_key:
            self.log("API Key belum diset! Pergi ke Settings.", "error")
            return

        btn_ref.configure(state="disabled", text="Processing...")
        self.log(f"Memulai proses... (Clips: {self.config['num_clips']})")
        
        gen_config = {
            "JUMLAH_KLIP": self.config['num_clips'],
            "FONT_SIZE": self.config['font_size']*3,
            "FONT_TYPE": self.config['font_family'],
            "FONT_COLOR": self.config['font_color'],
        }
        
        self.generator = KliperrGenerator(self.api_key, config=gen_config, logger_callback=self.log)
        threading.Thread(target=self._run_backend, args=(url, btn_ref, external_audio)).start()

    def _run_backend(self, url, btn_ref, external_audio=None):
        try:
            self.generator.run_process(url, external_audio=external_audio)
        except Exception as e:
            self.log(f"Critical Error: {e}", "error")
        finally:
            self.after(0, lambda: btn_ref.configure(state="normal", text="✨ Generate Shorts"))

    def cancel_process(self):
        if self.generator:
            self.generator.stop()

if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    app = KliperrApp()
    app.mainloop()
