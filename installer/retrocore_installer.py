from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from tkinter import Tk, StringVar, BooleanVar, filedialog, messagebox, ttk


APP_NAME = "Retrocore Installer"
PRODUCT_NAME = "Retrocore"
PUBLISHER = "Hivemind Studio"
URL = "https://hivemindstudio.art"
DEFAULT_INSTALL_DIR = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Retrocore"
PAYLOAD_NAME = "retrocore-package.zip"


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def add_to_system_path(directory: Path) -> None:
    import winreg

    key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        current, _ = winreg.QueryValueEx(key, "Path")
        parts = [part for part in current.split(";") if part]
        normalized = {part.rstrip("\\").lower() for part in parts}
        target = str(directory).rstrip("\\")
        if target.lower() not in normalized:
            parts.append(target)
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, ";".join(parts))

    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", SMTO_ABORTIFHUNG, 5000, None)


def write_cmd_launcher(install_dir: Path) -> None:
    launcher = install_dir / "retrocore.cmd"
    launcher.write_text('@echo off\r\nsetlocal\r\n"%~dp0retrocore.exe" %*\r\n', encoding="ascii")


class InstallerApp:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(APP_NAME)
        self.root.geometry("760x520")
        self.root.resizable(False, False)
        self.install_dir = StringVar(value=str(DEFAULT_INSTALL_DIR))
        self.add_to_path = BooleanVar(value=True)
        self.launch_manager = BooleanVar(value=True)
        self.step = 0
        self.payload_zip = self.resolve_payload_zip()
        self.status_var = StringVar(value="Ready to install.")
        self.build_ui()
        self.show_step(0)

    def resolve_payload_zip(self) -> Path:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        payload = base / PAYLOAD_NAME
        if not payload.exists():
            raise FileNotFoundError(f"Installer payload not found: {payload}")
        return payload

    def build_ui(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        palette = {"bg": "#000000", "fg": "#1aff1a", "border": "#1aff1a"}
        self.root.configure(bg=palette["bg"])
        style.configure(".", background=palette["bg"], foreground=palette["fg"], font=("Consolas", 10))
        style.configure("TFrame", background=palette["bg"])
        style.configure("TLabel", background=palette["bg"], foreground=palette["fg"])
        style.configure("TCheckbutton", background=palette["bg"], foreground=palette["fg"])
        style.configure("TButton", background=palette["bg"], foreground=palette["fg"], bordercolor=palette["border"])
        style.configure("Accent.TButton", background=palette["fg"], foreground=palette["bg"], bordercolor=palette["border"])
        style.configure("TEntry", fieldbackground=palette["bg"], foreground=palette["fg"])

        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        ttk.Label(header, text="RETROCORE INSTALLER", font=("Consolas", 20, "bold")).pack(anchor="w")
        ttk.Label(header, text="Retrocore by Hivemind Studio", font=("Consolas", 11)).pack(anchor="w")
        ttk.Label(header, text="Turn your terminal into a CRT.", font=("Consolas", 10)).pack(anchor="w")

        self.content = ttk.Frame(outer)
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.pages = [
            self.build_welcome_page(),
            self.build_options_page(),
            self.build_progress_page(),
        ]
        for page in self.pages:
            page.grid(row=0, column=0, sticky="nsew")

        footer = ttk.Frame(outer)
        footer.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        self.back_button = ttk.Button(footer, text="Back", command=self.go_back)
        self.back_button.grid(row=0, column=1, padx=(8, 0))
        self.next_button = ttk.Button(footer, text="Next", command=self.go_next, style="Accent.TButton")
        self.next_button.grid(row=0, column=2, padx=(8, 0))
        ttk.Button(footer, text="Cancel", command=self.root.destroy).grid(row=0, column=3, padx=(8, 0))

    def build_welcome_page(self):
        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Welcome", font=("Consolas", 16, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(
            frame,
            text=(
                "This wizard installs Retrocore, places it in Program Files, and can add the "
                "Retrocore command to the system PATH so you can run it from any terminal."
            ),
            wraplength=680,
            justify="left",
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "The installer also preserves writable Retrocore settings in your LocalAppData "
                "folder so the installed app can update presets and snapshots without editing "
                "files under Program Files."
            ),
            wraplength=680,
            justify="left",
        ).pack(anchor="w", pady=(12, 0))
        return frame

    def build_options_page(self):
        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Install Options", font=("Consolas", 16, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(frame, text="Install location").pack(anchor="w")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(6, 0))
        row.columnconfigure(0, weight=1)
        ttk.Entry(row, textvariable=self.install_dir).grid(row=0, column=0, sticky="ew")
        ttk.Button(row, text="Browse", command=self.browse_install_dir).grid(row=0, column=1, padx=(10, 0))
        ttk.Checkbutton(frame, text="Add Retrocore command to the system PATH", variable=self.add_to_path).pack(anchor="w", pady=(14, 0))
        ttk.Checkbutton(frame, text="Launch Retrocore Manager when setup finishes", variable=self.launch_manager).pack(anchor="w", pady=(6, 0))
        return frame

    def build_progress_page(self):
        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Installing", font=("Consolas", 16, "bold")).pack(anchor="w", pady=(0, 12))
        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.progress.pack(fill="x")
        self.log = ttk.Label(frame, text="", justify="left", wraplength=680)
        self.log.pack(anchor="w", pady=(12, 0))
        return frame

    def browse_install_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.install_dir.get() or str(DEFAULT_INSTALL_DIR))
        if chosen:
            self.install_dir.set(chosen)

    def show_step(self, step: int) -> None:
        self.step = step
        self.pages[step].tkraise()
        self.back_button.configure(state="normal" if step > 0 else "disabled")
        self.next_button.configure(text="Install" if step == 1 else "Next")
        if step == 2:
            self.back_button.configure(state="disabled")
            self.next_button.configure(state="disabled")

    def go_back(self) -> None:
        self.show_step(max(0, self.step - 1))

    def go_next(self) -> None:
        if self.step == 0:
            self.show_step(1)
            return
        if self.step == 1:
            self.show_step(2)
            self.root.after(50, self.run_install)

    def run_install(self) -> None:
        install_dir = Path(self.install_dir.get()).resolve()
        temp_dir = Path(tempfile.mkdtemp(prefix="retrocore-installer-"))
        try:
            self.set_progress(10, "Preparing install directory...")
            install_dir.mkdir(parents=True, exist_ok=True)

            self.set_progress(30, "Extracting Retrocore package...")
            with zipfile.ZipFile(self.payload_zip, "r") as archive:
                archive.extractall(temp_dir)

            self.set_progress(55, "Copying files...")
            payload_root = temp_dir / "retrocore"
            self.copy_tree(payload_root, install_dir)

            self.set_progress(72, "Writing command launcher...")
            write_cmd_launcher(install_dir)

            if self.add_to_path.get():
                self.set_progress(86, "Adding Retrocore to the system PATH...")
                add_to_system_path(install_dir)

            self.set_progress(100, "Installation complete.")
            self.status_var.set(f"Installed to {install_dir}")
            self.next_button.configure(text="Finish", state="normal", command=lambda: self.finish_install(install_dir))
            self.log.configure(text=f"Retrocore was installed to:\n{install_dir}")
        except Exception as exc:
            self.status_var.set("Installation failed.")
            self.log.configure(text=str(exc))
            messagebox.showerror(APP_NAME, str(exc))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def finish_install(self, install_dir: Path) -> None:
        if self.launch_manager.get():
            subprocess.Popen([str(install_dir / "retrocore.exe"), "manager"], cwd=str(install_dir))
        self.root.destroy()

    def copy_tree(self, source: Path, destination: Path) -> None:
        for item in source.rglob("*"):
            relative = item.relative_to(source)
            target = destination / relative
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)

    def set_progress(self, value: int, text: str) -> None:
        self.progress["value"] = value
        self.status_var.set(text)
        self.log.configure(text=text)
        self.root.update_idletasks()

    def run(self) -> int:
        self.root.mainloop()
        return 0


def main() -> int:
    if not is_admin():
        messagebox.showerror(APP_NAME, "Retrocore Installer must be run as administrator.")
        return 1
    return InstallerApp().run()


if __name__ == "__main__":
    raise SystemExit(main())
