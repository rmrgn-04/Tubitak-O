#!/usr/bin/env python3
"""
FPGA HDMI Kontrol Paneli
Video stream ve cozunurluk kontrolu.
Nexys Video FPGA karti uzerinden HDMI passthrough yapilan
goruntuyu UART (COM3) ile kontrol eder.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import serial
import threading
import time


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("FPGA HDMI Kontrol Paneli")
        self.root.geometry("540x280")
        self.root.resizable(True, True)
        self.root.configure(bg="#1a1b26")
        self.root.minsize(400, 250)

        self.ser = None
        self.lock = threading.Lock()
        self.connected = False
        self.com_port = tk.StringVar(value="COM3")
        self.status_text = tk.StringVar(value="Baglanti yok")

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _send(self, cmd, wait=1.5):
        if not self.connected or not self.ser:
            return ""
        with self.lock:
            try:
                self.ser.reset_input_buffer()
                self.ser.write(cmd.encode('ascii'))
                time.sleep(wait)
                data = self.ser.read(self.ser.in_waiting or 4096)
                return data.decode('ascii', errors='replace')
            except Exception as e:
                self.root.after(0, lambda: self.status_text.set(f"Hata: {e}"))
                return ""

    def _run(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def _toggle_connect(self):
        if self.connected:
            if self.ser:
                try:
                    self.ser.close()
                except:
                    pass
            self.ser = None
            self.connected = False
            self.btn_connect.configure(text="Baglan")
            self.status_text.set("Baglanti kesildi")
        else:
            try:
                self.ser = serial.Serial(self.com_port.get(), 115200, timeout=3, write_timeout=3)
                self.ser.reset_input_buffer()
                self.connected = True
                self.btn_connect.configure(text="Kes")
                self.status_text.set(f"{self.com_port.get()} bagli")
            except Exception as e:
                messagebox.showerror("Baglanti Hatasi", str(e))

    def _cmd_resolution(self, res_id, name):
        def task():
            self._send('1', wait=1.5)
            self._send(res_id, wait=3)
            self.root.after(0, lambda: self.status_text.set(f"Cozunurluk: {name}"))
        self._run(task)

    def _cmd_stream(self):
        def task():
            self._send('5', wait=2)
            self.root.after(0, lambda: self.status_text.set("Stream toggle gonderildi"))
        self._run(task)

    def _build_ui(self):
        BG = "#1a1b26"
        FG = "#c0caf5"
        ACCENT = "#7aa2f7"
        GREEN = "#9ece6a"

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=ACCENT,
                         font=("Segoe UI", 16, "bold"))
        style.configure("Status.TLabel", background=BG, foreground=GREEN,
                         font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI", 10), padding=5)
        style.configure("Stream.TButton", font=("Segoe UI", 13, "bold"), padding=10)
        style.configure("Res.TButton", font=("Segoe UI", 10), padding=6)
        style.configure("TLabelframe", background=BG, foreground=FG)
        style.configure("TLabelframe.Label", background=BG, foreground=ACCENT,
                         font=("Segoe UI", 10, "bold"))

        main = ttk.Frame(self.root, padding=14)
        main.pack(fill="both", expand=True)

        # ── Baslik + Baglanti ──
        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 10))

        ttk.Label(header, text="FPGA HDMI Kontrol",
                  style="Title.TLabel").pack(side="left")

        # Sag taraf: port + baglan + durum
        right = ttk.Frame(header)
        right.pack(side="right")
        ttk.Label(right, textvariable=self.status_text,
                  style="Status.TLabel").pack(side="right", padx=(8, 0))
        self.btn_connect = ttk.Button(right, text="Baglan",
                                       command=self._toggle_connect)
        self.btn_connect.pack(side="right", padx=4)
        ttk.Entry(right, textvariable=self.com_port, width=6,
                  font=("Segoe UI", 10)).pack(side="right")

        # ── Video Stream ──
        ttk.Button(main, text="VIDEO STREAM TOGGLE",
                   command=self._cmd_stream,
                   style="Stream.TButton").pack(fill="x", pady=(0, 10))

        # ── Cozunurluk ──
        res_frame = ttk.LabelFrame(main, text="Cikis Cozunurlugu", padding=8)
        res_frame.pack(fill="x")

        res_row = ttk.Frame(res_frame)
        res_row.pack(fill="x")

        resolutions = [
            ("640x480", "1"),
            ("800x600", "2"),
            ("720p", "3"),
            ("1280x1024", "4"),
            ("1080p", "5"),
        ]
        for i, (text, cmd) in enumerate(resolutions):
            ttk.Button(res_row, text=text, style="Res.TButton",
                       command=lambda c=cmd, t=text: self._cmd_resolution(c, t)).grid(
                row=0, column=i, padx=3, pady=2, sticky="ew")
            res_row.columnconfigure(i, weight=1)

    def _on_close(self):
        if self.ser:
            try:
                self.ser.close()
            except:
                pass
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
