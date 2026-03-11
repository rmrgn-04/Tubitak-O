#!/usr/bin/env python3
"""
FPGA HDMI Control Panel
Nexys Video HDMI Demo icin kullanici kontrol arayuzu.
FPGA uzerinden monitore giden goruntuyu UART (COM3) ile kontrol eder.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import serial
import threading
import time


class FPGAControlPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("FPGA HDMI Control Panel")
        self.root.geometry("600x480")
        self.root.resizable(True, True)
        self.root.configure(bg="#1e1e2e")

        self.ser = None
        self.lock = threading.Lock()
        self.connected = False
        self.stream_active = False

        self.current_resolution = tk.StringVar(value="---")
        self.current_capture = tk.StringVar(value="---")
        self.current_clock = tk.StringVar(value="---")
        self.current_display_fb = tk.StringVar(value="---")
        self.current_video_fb = tk.StringVar(value="---")
        self.status_text = tk.StringVar(value="Baglanti yok")
        self.com_port = tk.StringVar(value="COM3")

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        BG = "#1e1e2e"
        FG = "#cdd6f4"
        ACCENT = "#89b4fa"
        YELLOW = "#f9e2af"
        GREEN = "#a6e3a1"
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 9))
        style.configure("H.TLabel", background=BG, foreground=ACCENT, font=("Segoe UI", 12, "bold"))
        style.configure("V.TLabel", background=BG, foreground=YELLOW, font=("Segoe UI", 9))
        style.configure("S.TLabel", background=BG, foreground=GREEN, font=("Segoe UI", 8))
        style.configure("TButton", font=("Segoe UI", 9), padding=4)
        style.configure("Big.TButton", font=("Segoe UI", 10, "bold"), padding=6)
        style.configure("TLabelframe", background=BG, foreground=FG)
        style.configure("TLabelframe.Label", background=BG, foreground=ACCENT,
                         font=("Segoe UI", 9, "bold"))

        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        # ── Row 0: Title + Connection ──
        top = ttk.Frame(main)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="FPGA HDMI Control", style="H.TLabel").pack(side="left")
        ttk.Label(top, textvariable=self.status_text, style="S.TLabel").pack(side="right")
        self.btn_connect = ttk.Button(top, text="Baglan", command=self._toggle_connect)
        self.btn_connect.pack(side="right", padx=5)
        ttk.Entry(top, textvariable=self.com_port, width=6).pack(side="right")
        ttk.Label(top, text="Port:").pack(side="right", padx=(0, 3))

        # ── Row 1: Status (compact horizontal) ──
        sf = ttk.LabelFrame(main, text="Durum", padding=5)
        sf.pack(fill="x", pady=(0, 6))
        status_row = ttk.Frame(sf)
        status_row.pack(fill="x")
        for label, var in [("Display:", self.current_resolution),
                           ("Capture:", self.current_capture),
                           ("Clock:", self.current_clock)]:
            ttk.Label(status_row, text=label).pack(side="left", padx=(0, 2))
            ttk.Label(status_row, textvariable=var, style="V.TLabel").pack(side="left", padx=(0, 10))
        ttk.Button(status_row, text="Yenile", command=self._refresh_status).pack(side="right")

        # ── Row 2: Resolution buttons ──
        rf = ttk.LabelFrame(main, text="Cozunurluk (FPGA Cikis)", padding=5)
        rf.pack(fill="x", pady=(0, 6))
        res_row = ttk.Frame(rf)
        res_row.pack(fill="x")
        for i, (text, cmd) in enumerate([
            ("640x480", "1"), ("800x600", "2"), ("720p", "3"),
            ("1280x1024", "4"), ("1080p", "5"),
        ]):
            ttk.Button(res_row, text=text,
                       command=lambda c=cmd: self._set_resolution(c)).grid(
                row=0, column=i, padx=2, pady=2, sticky="ew")
            res_row.columnconfigure(i, weight=1)

        # ── Row 3: Stream + Frame ops (side by side) ──
        mid = ttk.Frame(main)
        mid.pack(fill="x", pady=(0, 6))

        # Stream
        stf = ttk.LabelFrame(mid, text="Video Stream", padding=5)
        stf.pack(side="left", fill="both", expand=True, padx=(0, 3))
        ttk.Button(stf, text="STREAM BASLAT / DURDUR",
                   command=self._toggle_stream, style="Big.TButton").pack(fill="x")

        # Framebuffer
        fbf = ttk.LabelFrame(mid, text="Framebuffer", padding=5)
        fbf.pack(side="left", fill="both", expand=True, padx=(3, 0))
        fb_row = ttk.Frame(fbf)
        fb_row.pack(fill="x")
        ttk.Button(fb_row, text="Display FB",
                   command=self._change_display_fb).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(fb_row, text="Video FB",
                   command=self._change_video_fb).pack(side="left", expand=True, fill="x", padx=1)

        # ── Row 4: Frame operations ──
        of = ttk.LabelFrame(main, text="Frame Islemleri", padding=5)
        of.pack(fill="x", pady=(0, 6))
        ops_row = ttk.Frame(of)
        ops_row.pack(fill="x")
        for i, (text, cmd) in enumerate([
            ("Renk Ters Cevir (1 frame)", self._invert_colors),
            ("Olcekle (Scale)", self._scale_frame),
            ("Test: Blend", self._test_blend),
            ("Test: Color Bar", self._test_colorbar),
        ]):
            ttk.Button(ops_row, text=text, command=cmd).grid(
                row=0, column=i, padx=2, pady=2, sticky="ew")
            ops_row.columnconfigure(i, weight=1)

        # ── Row 5: Info ──
        info = ttk.LabelFrame(main, text="Bilgi", padding=5)
        info.pack(fill="x", pady=(0, 0))
        ttk.Label(info, text="Not: Parlaklik/kontrast/anlik renk degisimi FPGA firmware desteklemiyor.",
                  foreground="#6c7086", font=("Segoe UI", 8)).pack(anchor="w")
        ttk.Label(info, text="Renk cevirme tek frame yakalar. Stream otomatik yeniden baslar.",
                  foreground="#6c7086", font=("Segoe UI", 8)).pack(anchor="w")

    # ── Serial ──

    def _send_command(self, cmd, wait=1.5):
        if not self.connected or not self.ser:
            return None
        with self.lock:
            try:
                self.ser.reset_input_buffer()
                self.ser.write(cmd.encode('ascii'))
                time.sleep(wait)
                data = self.ser.read(self.ser.in_waiting or 4096)
                return data.decode('ascii', errors='replace')
            except Exception as e:
                self.root.after(0, lambda: self._set_status(f"Hata: {e}"))
                return None

    def _parse_status(self, text):
        if not text:
            return
        for line in text.split('\n'):
            line = line.strip().strip('*')
            if 'Display Resolution:' in line:
                self.current_resolution.set(line.split(':', 1)[1].strip())
            elif 'Video Capture Resolution:' in line:
                self.current_capture.set(line.split(':', 1)[1].strip())
            elif 'Pixel Clock Freq' in line:
                self.current_clock.set(line.split(':', 1)[1].strip())
            elif 'Display Frame Index:' in line:
                self.current_display_fb.set(line.split(':', 1)[1].strip())
            elif 'Video Frame Index:' in line:
                self.current_video_fb.set(line.split(':', 1)[1].strip())

    def _set_status(self, text):
        self.status_text.set(text)

    # ── Actions ──

    def _toggle_connect(self):
        if self.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        try:
            port = self.com_port.get()
            self.ser = serial.Serial(port, 115200, timeout=3, write_timeout=3)
            self.ser.reset_input_buffer()
            self.connected = True
            self.btn_connect.configure(text="Kes")
            self._set_status(f"{port} bagli")
            self.root.after(500, self._refresh_status)
        except Exception as e:
            messagebox.showerror("Baglanti Hatasi", str(e))

    def _disconnect(self):
        if self.ser:
            try:
                self.ser.close()
            except:
                pass
        self.ser = None
        self.connected = False
        self.btn_connect.configure(text="Baglan")
        self._set_status("Baglanti yok")

    def _run(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def _refresh_status(self):
        def task():
            resp = self._send_command('\r', wait=1.5)
            if resp:
                self.root.after(0, lambda: self._parse_status(resp))
                self.root.after(0, lambda: self._set_status("Guncellendi"))
        self._run(task)

    def _set_resolution(self, res_id):
        def task():
            self._send_command('1', wait=1.5)
            resp = self._send_command(res_id, wait=3)
            if resp:
                self.root.after(0, lambda: self._parse_status(resp))
                self.root.after(0, lambda: self._set_status("Cozunurluk degistirildi"))
        self._run(task)

    def _toggle_stream(self):
        def task():
            resp = self._send_command('5', wait=2)
            self.stream_active = not self.stream_active
            if resp:
                self.root.after(0, lambda: self._parse_status(resp))
            s = "Stream aktif" if self.stream_active else "Stream durduruldu"
            self.root.after(0, lambda: self._set_status(s))
        self._run(task)

    def _restart_stream(self):
        if self.stream_active:
            self._send_command('5', wait=1)
            time.sleep(0.3)
        self._send_command('5', wait=1)
        self.stream_active = True

    def _invert_colors(self):
        def task():
            self._send_command('7', wait=2)
            self._restart_stream()
            self.root.after(0, lambda: self._set_status("Renkler cevrildi + stream basladi"))
            resp = self._send_command('\r', wait=1)
            if resp:
                self.root.after(0, lambda: self._parse_status(resp))
        self._run(task)

    def _scale_frame(self):
        def task():
            self._send_command('8', wait=2)
            self._restart_stream()
            self.root.after(0, lambda: self._set_status("Olceklendi + stream basladi"))
            resp = self._send_command('\r', wait=1)
            if resp:
                self.root.after(0, lambda: self._parse_status(resp))
        self._run(task)

    def _test_blend(self):
        def task():
            self._send_command('3', wait=2)
            self.root.after(0, lambda: self._set_status("Blend test pattern"))
        self._run(task)

    def _test_colorbar(self):
        def task():
            self._send_command('4', wait=2)
            self.root.after(0, lambda: self._set_status("Color bar test pattern"))
        self._run(task)

    def _change_display_fb(self):
        def task():
            resp = self._send_command('2', wait=2)
            if resp:
                self.root.after(0, lambda: self._parse_status(resp))
                self.root.after(0, lambda: self._set_status("Display FB degisti"))
        self._run(task)

    def _change_video_fb(self):
        def task():
            resp = self._send_command('6', wait=2)
            if resp:
                self.root.after(0, lambda: self._parse_status(resp))
                self.root.after(0, lambda: self._set_status("Video FB degisti"))
        self._run(task)

    def _on_close(self):
        self._disconnect()
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    app = FPGAControlPanel(root)
    root.mainloop()
