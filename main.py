import customtkinter as ctk
import yt_dlp
import os
import re
import shutil
from threading import Thread
from queue import Queue, Empty

from tkinter import messagebox, filedialog  # Import filedialog

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window configuration
        self.title("YouTube MP3/MP4 Converter")
        self.geometry("800x600")
        # Theme configuration
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Queue for thread-safe communication
        self.queue = Queue()

        # Main frame
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(padx=20, pady=20, fill="both", expand=True)

        # URL Input
        self.url_label = ctk.CTkLabel(self.main_frame, text="YouTube URL:")
        self.url_label.pack(pady=10)

        self.url_entry = ctk.CTkEntry(self.main_frame, width=400)
        self.url_entry.pack(pady=10)

        # Format buttons
        self.format_frame = ctk.CTkFrame(self.main_frame)
        self.format_frame.pack(pady=20)

        self.format_var = ctk.StringVar(value="video")
        self.video_radio = ctk.CTkRadioButton(
            self.format_frame, text="Video (MP4)", variable=self.format_var, value="video", command=self.update_quality_options
        )
        self.video_radio.pack(side="left", padx=10)

        self.audio_radio = ctk.CTkRadioButton(
            self.format_frame, text="Audio (MP3)", variable=self.format_var, value="audio", command=self.update_quality_options
        )
        self.audio_radio.pack(side="left", padx=10)

        # Quality dropdown
        self.quality_label = ctk.CTkLabel(self.main_frame, text="Quality:")
        self.quality_label.pack(pady=5)

        self.quality_var = ctk.StringVar(value="720p")
        self.quality_dropdown = ctk.CTkOptionMenu(
            self.main_frame, variable=self.quality_var, values=["360p", "480p", "720p", "1080p"]
        )
        self.quality_dropdown.pack(pady=10)

        # Download folder selection
        self.download_folder_label = ctk.CTkLabel(self.main_frame, text="Download Folder:")
        self.download_folder_label.pack(pady=10)

        self.download_folder_entry = ctk.CTkEntry(self.main_frame, width=400)
        self.download_folder_entry.pack(pady=10)

        self.select_folder_button = ctk.CTkButton(
            self.main_frame, text="Select Download Folder", command=self.select_download_folder
        )
        self.select_folder_button.pack(pady=10)

        # Initialize download folder path
        self.download_folder = os.path.join(os.path.expanduser('~'), 'Downloads')  # Default to user's Downloads folder
        self.download_folder_entry.insert(0, self.download_folder)  # Set initial path in entry

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self.main_frame)
        self.progress_bar.pack(pady=10)

        # Status label
        self.status_label = ctk.CTkLabel(self.main_frame, text="Status: Idle")
        self.status_label.pack(pady=10)

        # Download button
        self.download_button = ctk.CTkButton(
            self.main_frame, text="Download", command=self.start_download
        )
        self.download_button.pack(pady=20)
        self.download_button.configure(state="disabled")  # Initially disable the button

        # URL validation
        self.url_entry.bind("<KeyRelease>", self.validate_url)

        # Start processing the queue
        self.process_queue()

    def select_download_folder(self):
        folder_selected = filedialog.askdirectory()  # Open folder selection dialog
        if folder_selected:
            self.download_folder = folder_selected  # Update the download folder path
            self.download_folder_entry.delete(0, ctk.END)  # Clear the entry
            self.download_folder_entry.insert(0, self.download_folder)  # Set the selected path

    def update_quality_options(self):
        """Updates the quality dropdown options based on the selected format."""
        if self.format_var.get() == "video":
            self.quality_var.set("720p")  # Default for video
            self.quality_dropdown.configure(values=["360p", "480p", "720p", "1080p"])
        else:  # Audio
            self.quality_var.set("192kbps")  # Default for audio
            self.quality_dropdown.configure(values=["128kbps", "192kbps", "256kbps", "320kbps"])

    def validate_url(self, event):
        url = self.url_entry.get()
        youtube_regex = r"^(https?://)?(www\.)?(youtube\.com|youtu\.?be)/.+$"
        if re.match(youtube_regex, url):
            self.download_button.configure(state="normal")
        else:
            self.download_button.configure(state="disabled")

    def get_ffmpeg_path(self):
        """Checks for FFmpeg executable."""
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return ffmpeg_path

        # Check for ffmpeg.exe in the current directory (for Windows)
        if os.path.exists("ffmpeg.exe"):
            return "ffmpeg.exe"
            
        return None

    def process_queue(self):
        """Processes the queue for thread-safe GUI updates."""
        try:
            while True:
                task, value = self.queue.get_nowait()
                if task == "progress":
                    self.progress_bar.set(value)
                    self.status_label.configure(text=f"Downloading: {value * 100:.1f}%")
                elif task == "status":
                    self.status_label.configure(text=value)
                    if "completed" in value.lower() or "error" in value.lower():
                        self.download_button.configure(state="normal")
        except Empty:
            pass
        finally:
            self.after(100, self.process_queue)  # Schedule next check

    def download_with_ytdlp(self, url):
        output_template = os.path.join(self.download_folder, "%(title)s.%(ext)s")

        if self.format_var.get() == "video":
            quality = self.quality_var.get().rstrip("p")
            format_spec = f"bestvideo[height<={quality}]+bestaudio/best"
            ffmpeg_location = None
        else:
            format_spec = "bestaudio/best"
            output_template = os.path.join(self.download_folder, "%(title)s.mp3")

            ffmpeg_location = self.get_ffmpeg_path()
            if not ffmpeg_location:
                self.queue.put(("status", "Error: FFmpeg not found."))
                messagebox.showerror("Error", "FFmpeg not found. Please install FFmpeg and ensure it's in your system's PATH or in the application's folder.")
                return

        ydl_opts = {
            "format": format_spec,
            "progress_hooks": [self.progress_hook],
            "outtmpl": output_template,
            "quiet": False,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9"
            },
            "ffmpeg_location": ffmpeg_location,
            "cookiefile": "cookies.txt" if os.path.exists("cookies.txt") else None,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }] if self.format_var.get() == "audio" else []
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            self.queue.put(("status", "Download completed successfully!"))
        except Exception as e:
            self.queue.put(("status", f"Error: {str(e)}"))

    def progress_hook(self, d):
        if d["status"] == "downloading":
            try:
                total = d.get("total_bytes", 0) or d.get("total_bytes_estimate", 0)
                if total > 0:
                    downloaded = d.get("downloaded_bytes", 0)
                    progress = downloaded / total
                    self.queue.put(("progress", progress))
            except Exception:
                pass
        elif d["status"] == "finished":
            self.queue.put(("status", "Finalizing..."))
            
    def start_download(self):
        url = self.url_entry.get()
        self.download_button.configure(state="disabled")
        self.status_label.configure(text="Starting download...")

        # Create downloads folder if it doesn't exist
        if not os.path.exists("downloads"):
            os.makedirs("downloads")

        download_thread = Thread(target=self.download_with_ytdlp, args=(url,))
        download_thread.start()

if __name__ == "__main__":
    app = App()
    app.mainloop()
