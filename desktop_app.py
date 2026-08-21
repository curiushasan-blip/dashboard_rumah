"""
desktop_app.py
================
Menjalankan Dasbor Komparasi Rumah sebagai jendela aplikasi tersendiri --
tanpa tab browser biasa, tanpa perlu buka VSCode setiap kali mau memakainya,
dan TANPA dependency tambahan yang rewel (tidak pakai pywebview).

Triknya: Streamlit dijalankan sebagai server lokal di baliknya, lalu dibuka
memakai mode "--app" milik Microsoft Edge / Google Chrome -- mode ini
menampilkan halaman tanpa address bar, tab, atau menu, persis seperti
jendela aplikasi biasa, memakai browser yang sudah pasti terpasang di
Windows (Edge bawaan) tanpa perlu instalasi apa pun lagi.

Cara pakai sehari-hari: double-click file "Buka Dasbor Rumah.bat" (atau
shortcut yang Anda buat dari file itu). VSCode hanya dibutuhkan SATU KALI
di awal untuk instalasi -- lihat README.md bagian
"Menjalankan sebagai Aplikasi Desktop".

Sebelum menyalakan server, skrip ini juga mengecek apakah semua library
wajib (streamlit, folium, dst) sudah terpasang untuk Python yang SAMA
persis dengan yang menjalankan file ini -- kalau belum, akan muncul pesan
jelas berisi path Python yang dipakai & perintah pasti untuk instalnya,
alih-alih error yang membingungkan.

Jika jendela gagal muncul, jalankan "Buka Dasbor Rumah (debug).bat" untuk
melihat pesan error langsung, atau cek file desktop_app.log dan
streamlit_server.log di folder ini.
"""

import logging
import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PORT = 8765
LOG_PATH = APP_DIR / "desktop_app.log"
STREAMLIT_LOG_PATH = APP_DIR / "streamlit_server.log"
BROWSER_PROFILE_DIR = APP_DIR / ".browser_profile"

REQUIRED_MODULES = ["streamlit", "folium", "streamlit_folium", "pandas", "plotly"]

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def _check_dependencies():
    """Cek apakah semua library wajib bisa di-import oleh Python yang SAMA
    persis dengan yang akan dipakai untuk menjalankan server Streamlit
    (sys.executable). Ini menghindari kebingungan 'sudah pip install tapi
    masih ModuleNotFoundError' yang biasanya disebabkan oleh pip install
    dan python yang menjalankan aplikasi ternyata dua interpreter berbeda."""
    missing = []
    for mod_name in REQUIRED_MODULES:
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(mod_name)
    return missing


def _port_is_open(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _start_streamlit():
    """Jalankan server Streamlit sebagai proses terpisah, tanpa jendela console."""
    cmd = [
        sys.executable, "-m", "streamlit", "run", str(APP_DIR / "app.py"),
        "--server.port", str(PORT),
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--global.developmentMode", "false",
    ]
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    logging.info("Menjalankan server Streamlit: %s", " ".join(cmd))
    log_file = open(STREAMLIT_LOG_PATH, "w", encoding="utf-8")
    return subprocess.Popen(
        cmd, cwd=str(APP_DIR), stdout=log_file, stderr=subprocess.STDOUT, **kwargs
    )


def _wait_for_server(timeout=40):
    start = time.time()
    while time.time() - start < timeout:
        if _port_is_open(PORT):
            return True
        time.sleep(0.3)
    return False


def _find_app_mode_browser():
    """Cari Edge atau Chrome yang terpasang, untuk dipakai mode --app (tampilan
    tanpa address bar/tab, seperti aplikasi native)."""
    if sys.platform == "win32":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local = os.environ.get("LocalAppData", "")
        candidates = [
            fr"{pf}\Microsoft\Edge\Application\msedge.exe",
            fr"{pf86}\Microsoft\Edge\Application\msedge.exe",
            fr"{pf}\Google\Chrome\Application\chrome.exe",
            fr"{pf86}\Google\Chrome\Application\chrome.exe",
            fr"{local}\Google\Chrome\Application\chrome.exe",
            fr"{local}\Microsoft\Edge\Application\msedge.exe",
        ]
    elif sys.platform == "darwin":
        candidates = [
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]
    else:
        candidates = [
            "/usr/bin/microsoft-edge", "/usr/bin/microsoft-edge-stable",
            "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium-browser", "/usr/bin/chromium",
        ]

    for path in candidates:
        if path and Path(path).exists():
            return path
    return None


def _notify_user(title, message):
    """Tampilkan pesan ke pengguna lewat dialog tkinter (bawaan Python), dan
    selalu dicatat juga ke desktop_app.log & dicetak ke console (untuk mode debug)."""
    logging.error("%s -- %s", title, message)
    print(f"{title}\n{message}")
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        logging.exception("Gagal menampilkan dialog tkinter")


def main():
    logging.info("Memulai Dasbor Komparasi Rumah (mode desktop)...")
    logging.info("Python yang dipakai: %s", sys.executable)

    missing = _check_dependencies()
    if missing:
        msg = (
            f"Library berikut belum terpasang untuk Python yang menjalankan aplikasi ini:\n"
            f"{', '.join(missing)}\n\n"
            f"Python yang dipakai:\n{sys.executable}\n\n"
            "Cara memperbaiki -- buka Command Prompt / PowerShell, lalu jalankan PERSIS "
            "perintah berikut (bukan sekadar 'pip install', supaya dijamin memakai Python "
            "yang sama):\n\n"
            f'"{sys.executable}" -m pip install -r "{APP_DIR / "requirements.txt"}"\n\n'
            "Setelah selesai tanpa error, coba buka aplikasi lagi."
        )
        _notify_user("Dasbor Komparasi Rumah \u2014 Library Belum Lengkap", msg)
        return

    proc = _start_streamlit()
    try:
        if not _wait_for_server():
            msg = (
                "Server Streamlit tidak merespons dalam waktu yang ditentukan.\n\n"
                "Cek file streamlit_server.log di folder ini untuk detail errornya "
                "(kemungkinan besar ada library yang belum terpasang -- jalankan "
                "'pip install -r requirements.txt')."
            )
            _notify_user("Dasbor Komparasi Rumah \u2014 Gagal Memuat", msg)
            return

        url = f"http://127.0.0.1:{PORT}"
        browser_exe = _find_app_mode_browser()

        if browser_exe:
            BROWSER_PROFILE_DIR.mkdir(exist_ok=True)
            cmd = [
                browser_exe,
                f"--app={url}",
                f"--user-data-dir={BROWSER_PROFILE_DIR}",
                "--window-size=1320,840",
                "--no-first-run",
                "--no-default-browser-check",
            ]
            logging.info("Membuka jendela aplikasi: %s", " ".join(cmd))
            try:
                browser_proc = subprocess.Popen(cmd)
                browser_proc.wait()
                logging.info("Jendela aplikasi ditutup oleh pengguna.")
            except Exception:
                logging.exception("Gagal membuka browser dalam mode app, memakai fallback tab biasa")
                browser_exe = None

        if not browser_exe:
            logging.warning("Edge/Chrome tidak ditemukan, membuka di browser default sebagai tab biasa.")
            print(f"Edge/Chrome tidak ditemukan. Membuka {url} di browser default...")
            print("Biarkan jendela ini tetap terbuka selama memakai aplikasi.")
            webbrowser.open(url)
            try:
                proc.wait()
            except KeyboardInterrupt:
                pass
    finally:
        logging.info("Menghentikan server Streamlit...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
