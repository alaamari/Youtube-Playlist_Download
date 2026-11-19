"""Small Windows desktop window for the bundled MediaFlow download engine."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

VERSION = "1.4.0"
APP_NAME = "MediaFlow"


def app_root():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]


class MediaFlowWindow:
    def __init__(self, root):
        self.root = root
        self.root.title(f"MediaFlow {VERSION}")
        self.root.geometry("570x460")
        self.root.minsize(520, 430)
        self.root.configure(bg="#101512")
        self.events = queue.Queue()
        self.process = None
        self.worker = None
        self.cancel_requested = False
        self.saved_count = 0
        self.data_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.data_dir / "settings.json"
        self.settings = self._load_settings()
        self.url_var = tk.StringVar()
        self.url_var.trace_add("write", lambda *_: self._update_provider_options())
        self.destination_var = tk.StringVar(value=self.settings.get("destination", str(Path.home() / "Music")))
        self.format_var = tk.StringVar(value=self.settings.get("format", "mp3"))
        self.playlist_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready. Your downloads stay on this computer.")
        self._build_ui()
        self._poll_events()

    def _load_settings(self):
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_settings(self):
        self.settings_path.write_text(json.dumps({"destination": self.destination_var.get(), "format": self.format_var.get()}, indent=2), encoding="utf-8")

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#101512")
        style.configure("TLabel", background="#101512", foreground="#e9eee9", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 23), foreground="#f3fff5")
        style.configure("Hint.TLabel", foreground="#a5b1a8")
        style.configure("TEntry", fieldbackground="#1b241e", foreground="#f2f5f2", insertcolor="#ffffff", bordercolor="#39483c")
        style.configure("TCombobox", fieldbackground="#1b241e", foreground="#f2f5f2", arrowcolor="#f2f5f2")
        style.configure("TCheckbutton", background="#101512", foreground="#d7ded8")
        style.map("TCheckbutton", background=[("active", "#101512")])
        style.configure("Primary.TButton", font=("Segoe UI Semibold", 11), padding=(16, 10), background="#2ca456", foreground="white", borderwidth=0)
        style.map("Primary.TButton", background=[("active", "#36b865"), ("disabled", "#315640")])
        style.configure("Secondary.TButton", padding=(12, 8), background="#27332b", foreground="#edf3ed", borderwidth=0)
        style.map("Secondary.TButton", background=[("active", "#344339")])

        frame = ttk.Frame(self.root, padding=(28, 24, 28, 20))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="MediaFlow", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Save songs one by one from YouTube or Spotify", style="Hint.TLabel").pack(anchor="w", pady=(2, 23))

        ttk.Label(frame, text="Playlist, album, or video link").pack(anchor="w", pady=(0, 6))
        self.url_entry = ttk.Entry(frame, textvariable=self.url_var, font=("Segoe UI", 10))
        self.url_entry.pack(fill="x", ipady=7)
        self.url_entry.focus_set()

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(17, 0))
        ttk.Label(row, text="Audio format").pack(side="left")
        self.format_menu = ttk.Combobox(row, textvariable=self.format_var, values=("mp3", "m4a", "flac", "mp4"), state="readonly", width=10)
        self.format_menu.pack(side="left", padx=(12, 0))
        self.format_menu.bind("<<ComboboxSelected>>", lambda _event: self._update_provider_options())
        self.playlist_check = ttk.Checkbutton(row, text="Download full YouTube playlist", variable=self.playlist_var)
        self.playlist_check.pack(side="left", padx=(20, 0))

        ttk.Label(frame, text="Save to").pack(anchor="w", pady=(19, 6))
        dest_row = ttk.Frame(frame)
        dest_row.pack(fill="x")
        ttk.Entry(dest_row, textvariable=self.destination_var).pack(side="left", fill="x", expand=True, ipady=7)
        ttk.Button(dest_row, text="Choose folder…", style="Secondary.TButton", command=self._choose_folder).pack(side="left", padx=(8, 0))

        self.status_label = ttk.Label(frame, textvariable=self.status_var, style="Hint.TLabel", wraplength=505, justify="left")
        self.status_label.pack(anchor="w", fill="x", pady=(22, 12))
        self.progress = ttk.Progressbar(frame, mode="indeterminate", length=500)
        self.progress.pack(fill="x")
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(17, 0))
        self.download_button = ttk.Button(buttons, text="Download", style="Primary.TButton", command=self._start)
        self.download_button.pack(side="left")
        self.cancel_button = ttk.Button(buttons, text="Cancel", style="Secondary.TButton", command=self._cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=(9, 0))
        ttk.Label(frame, text=f"Version {VERSION} · Windows 10 or later · x64", style="Hint.TLabel").pack(anchor="w", side="bottom", pady=(18, 0))

    def _choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.destination_var.get() or str(Path.home()), title="Choose download folder")
        if folder:
            self.destination_var.set(folder)
            self._save_settings()

    def _update_provider_options(self):
        spotify = "spotify.com/" in self.url_var.get().lower()
        if spotify:
            self.format_menu.configure(values=("mp3", "m4a", "flac"))
            if self.format_var.get() == "mp4":
                self.format_var.set("mp3")
            self.playlist_check.configure(state="disabled")
        else:
            self.format_menu.configure(values=("mp3", "m4a", "flac", "mp4"))
            self.playlist_check.configure(state="normal")

    def _start(self):
        url = self.url_var.get().strip()
        dest = self.destination_var.get().strip()
        if not url:
            messagebox.showinfo(APP_NAME, "Paste a YouTube or Spotify link first.")
            return
        if not dest:
            messagebox.showinfo(APP_NAME, "Choose where to save your downloads.")
            return
        engine = app_root() / "engine" / "mediaflow-engine.exe"
        if not engine.is_file():
            messagebox.showerror(APP_NAME, "The download engine is missing. Extract the full MediaFlow folder, then open MediaFlow.exe again.")
            return
        self._save_settings()
        self.saved_count = 0
        self.cancel_requested = False
        self.download_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.progress.start(12)
        self.status_var.set("Starting your download…")
        config = {"url": url, "format": self.format_var.get(), "playlist": self.playlist_var.get(), "destination": dest, "data": str(self.data_dir)}
        self.worker = threading.Thread(target=self._run_engine, args=(str(engine), config), daemon=True)
        self.worker.start()

    def _run_engine(self, engine, config):
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.process = subprocess.Popen([engine, "--worker"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=creation_flags)
            self.process.stdin.write(json.dumps(config) + "\n")
            self.process.stdin.flush()
            self.process.stdin.close()
            for line in self.process.stdout:
                try:
                    self.events.put(json.loads(line))
                except ValueError:
                    self.events.put({"type": "progress", "message": line.strip()})
            self.process.wait()
            if self.cancel_requested:
                self.events.put({"type": "done", "state": "cancelled", "message": f"Download cancelled. {self.saved_count} song(s) already saved remain in your folder."})
        except Exception as exc:
            self.events.put({"type": "done", "state": "error", "message": str(exc)})
        finally:
            self.process = None

    def _cancel(self):
        if not self.process:
            return
        self.cancel_requested = True
        self.status_var.set("Stopping the current download…")
        pid = self.process.pid
        def stop_tree():
            try:
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                pass
        threading.Thread(target=stop_tree, daemon=True).start()

    def _poll_events(self):
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = event.get("type")
            if kind == "status":
                self.status_var.set(event.get("message", "Working…"))
            elif kind == "progress":
                text = event.get("message", "Working…")
                self.status_var.set(text[-180:] if len(text) > 180 else text)
            elif kind == "saved":
                self.saved_count = max(self.saved_count, int(event.get("count", self.saved_count + 1)))
                self.status_var.set(f"Saved {self.saved_count} song(s) so far: {event.get('name', '')}")
            elif kind == "done":
                self.progress.stop()
                self.download_button.configure(state="normal")
                self.cancel_button.configure(state="disabled")
                self.status_var.set(event.get("message", "Finished."))
                state = event.get("state")
                if state == "error":
                    messagebox.showerror("Download could not finish", event.get("message", "Please check the link and try again."))
                elif state == "complete":
                    messagebox.showinfo(APP_NAME, event.get("message", "Download complete."))
        self.root.after(100, self._poll_events)


def main():
    root = tk.Tk()
    MediaFlowWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
