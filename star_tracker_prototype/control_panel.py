#!/usr/bin/env python3
"""
FPGA HDMI + Star Tracker Kontrol Paneli
========================================
Nexys Video FPGA karti uzerinden:
  - HDMI cikis cozunurluk kontrolu
  - Video stream baslatma/durdurma
  - Test pattern secimi
  - Renk inversiyonu / frame olcekleme
  - Star Tracker: yildiz tespiti + overlay cizimi
  - Threshold ayarlama
  - Sonuclari canli izleme
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial
import threading
import time
import sys
import os
import numpy as np
from PIL import Image, ImageTk


class StarTrackerPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("FPGA HDMI + Star Tracker Kontrol Paneli")
        self.root.geometry("820x940")
        self.root.resizable(True, True)
        self.root.configure(bg="#0B1D3A")
        self.root.minsize(700, 600)

        self.ser = None
        self.lock = threading.Lock()
        self.connected = False
        self.com_port = tk.StringVar(value="COM3")
        self.status_text = tk.StringVar(value="Baglanti yok")
        self.threshold_var = tk.IntVar(value=50)
        self.stars_detected = tk.StringVar(value="0")
        self.resolution_var = tk.StringVar(value="640x480")

        self.current_lut = tk.StringVar(value="Grayscale")
        self.star_img_tk = None  # PhotoImage referansını tutmak için
        self.last_stars = []     # Son tespit edilen yıldızlar
        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UART Haberlesme ──

    def _send(self, cmd, wait=1.5):
        """UART komutu gonder ve cevabi oku."""
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

    def _send_long(self, cmd, timeout=90, end_marker=None):
        """Uzun sureli UART komutu - Star Tracker icin."""
        if not self.connected or not self.ser:
            return ""
        with self.lock:
            try:
                self.ser.reset_input_buffer()
                self.ser.write(cmd.encode('ascii'))
                buf = ""
                start = time.time()
                while time.time() - start < timeout:
                    data = self.ser.read(self.ser.in_waiting or 1)
                    if data:
                        text = data.decode('ascii', errors='replace')
                        buf += text
                        # Log'a yaz
                        self.root.after(0, lambda t=text: self._log_append(t))
                        if end_marker and end_marker in buf:
                            break
                return buf
            except Exception as e:
                self.root.after(0, lambda: self.status_text.set(f"Hata: {e}"))
                return ""

    def _run(self, fn):
        """Fonksiyonu arka plan thread'inde calistir."""
        threading.Thread(target=fn, daemon=True).start()

    # ── Baglanti ──

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
            self._set_buttons_state("disabled")
        else:
            try:
                self.ser = serial.Serial(self.com_port.get(), 115200,
                                         timeout=2, write_timeout=3)
                self.ser.reset_input_buffer()
                self.connected = True
                self.btn_connect.configure(text="Kes")
                self.status_text.set(f"{self.com_port.get()} bagli")
                self._set_buttons_state("normal")
                # Baslangic menusunu oku
                self._run(self._read_initial_menu)
            except Exception as e:
                messagebox.showerror("Baglanti Hatasi", str(e))

    def _read_initial_menu(self):
        time.sleep(0.5)
        resp = self._send('', wait=1)
        if '1920' in resp:
            self.root.after(0, lambda: self.resolution_var.set("1920x1080"))
        elif '1280x720' in resp:
            self.root.after(0, lambda: self.resolution_var.set("1280x720"))
        elif '800x600' in resp:
            self.root.after(0, lambda: self.resolution_var.set("800x600"))
        self._log_append(resp)

    def _set_buttons_state(self, state):
        for btn in self.all_buttons:
            try:
                btn.configure(state=state)
            except:
                pass

    # ── Display / Video Komutlari ──

    def _cmd_resolution(self, res_id, name):
        def task():
            self._log_clear()
            self._log_append(f"Cozunurluk degistiriliyor: {name}...\n")
            self._send('1', wait=1.5)
            resp = self._send(res_id, wait=3)
            self._log_append(resp)
            self.root.after(0, lambda: self.resolution_var.set(name))
            self.root.after(0, lambda: self.status_text.set(f"Cozunurluk: {name}"))
        self._run(task)

    def _cmd_stream_toggle(self):
        def task():
            self._log_append("Video stream toggle...\n")
            resp = self._send('5', wait=2)
            self._log_append(resp)
            self.root.after(0, lambda: self.status_text.set("Stream toggle"))
        self._run(task)

    def _cmd_test_pattern(self, pattern_id):
        names = {'3': 'Blended', '4': 'Color Bar'}
        def task():
            self._log_append(f"Test pattern: {names.get(pattern_id, '?')}...\n")
            resp = self._send(pattern_id, wait=2)
            self._log_append(resp)
            self.root.after(0, lambda: self.status_text.set(
                f"Pattern: {names.get(pattern_id, '?')}"))
        self._run(task)

    # ── False Color LUT ──

    def _build_lut(self, name):
        """256 elemanlı LUT tablosu oluştur: her eleman (R,G,B) tuple."""
        lut = np.zeros((256, 3), dtype=np.uint8)
        for i in range(256):
            t = i / 255.0
            if name == "Grayscale":
                lut[i] = [i, i, i]
            elif name == "Heatmap":
                # siyah → kırmızı → sarı → beyaz
                if t < 0.33:
                    s = t / 0.33
                    lut[i] = [int(255 * s), 0, 0]
                elif t < 0.66:
                    s = (t - 0.33) / 0.33
                    lut[i] = [255, int(255 * s), 0]
                else:
                    s = (t - 0.66) / 0.34
                    lut[i] = [255, 255, int(255 * s)]
            elif name == "Rainbow":
                # mavi → cyan → yeşil → sarı → kırmızı
                if t < 0.25:
                    s = t / 0.25
                    lut[i] = [0, int(255 * s), 255]
                elif t < 0.5:
                    s = (t - 0.25) / 0.25
                    lut[i] = [0, 255, int(255 * (1 - s))]
                elif t < 0.75:
                    s = (t - 0.5) / 0.25
                    lut[i] = [int(255 * s), 255, 0]
                else:
                    s = (t - 0.75) / 0.25
                    lut[i] = [255, int(255 * (1 - s)), 0]
            elif name == "Inverted":
                v = 255 - i
                lut[i] = [v, v, v]
        return lut

    def _apply_lut_to_canvas(self, lut_name=None):
        """Starfield preview görüntüsüne LUT uygulayıp canvas'ta göster."""
        if lut_name:
            self.current_lut.set(lut_name)
        else:
            lut_name = self.current_lut.get()

        # Preview PNG'yi yükle
        preview_path = os.path.join(self.script_dir, "starfield_preview.png")
        if not os.path.exists(preview_path):
            self._log_append("starfield_preview.png bulunamadi!\n")
            return

        gray = np.array(Image.open(preview_path).convert('L'))

        # LUT uygula
        lut = self._build_lut(lut_name)
        h, w = gray.shape
        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        rgb[..., 0] = lut[gray, 0]
        rgb[..., 1] = lut[gray, 1]
        rgb[..., 2] = lut[gray, 2]

        # Canvas boyutuna küçült
        canvas = self.star_canvas
        canvas.update_idletasks()
        cw = canvas.winfo_width() or 380
        ch = canvas.winfo_height() or 220

        img = Image.fromarray(rgb)
        # En-boy oranını koru
        scale = min(cw / w, ch / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = img.resize((new_w, new_h), Image.NEAREST)

        self.star_img_tk = ImageTk.PhotoImage(img)

        canvas.delete("all")
        ox = (cw - new_w) // 2
        oy = (ch - new_h) // 2
        canvas.create_image(ox, oy, anchor="nw", image=self.star_img_tk)

        # Aktif LUT adını göster
        canvas.create_text(ox + 5, oy + 5, anchor="nw", text=lut_name,
                           fill="#FFD700", font=("Segoe UI", 9, "bold"))

        # Üzerine yıldız işaretlerini çiz (varsa)
        if self.last_stars:
            self._draw_star_overlay(canvas, ox, oy, new_w, new_h, w, h)

        self.root.after(0, lambda: self.status_text.set(f"False Color: {lut_name}"))

    def _draw_star_overlay(self, canvas, ox, oy, disp_w, disp_h, img_w, img_h):
        """Yıldız işaretlerini LUT görüntüsünün üzerine çiz."""
        res = self.resolution_var.get()
        if '1920' in res or '1080' in res:
            src_w, src_h = 1920, 1080
        elif '1280' in res:
            src_w, src_h = 1280, 720 if '720' in res else 1024
        elif '800' in res:
            src_w, src_h = 800, 600
        else:
            src_w, src_h = 640, 480

        sx = disp_w / src_w
        sy = disp_h / src_h

        for sid, x, y, brightness, pixels, peak in self.last_stars:
            cx = ox + x * sx
            cy = oy + y * sy
            r = max(4, min(10, pixels * 0.5))
            # İnce crosshair
            canvas.create_line(cx - r - 2, cy, cx + r + 2, cy,
                               fill="#FF4444", width=1)
            canvas.create_line(cx, cy - r - 2, cx, cy + r + 2,
                               fill="#FF4444", width=1)
            canvas.create_text(cx + r + 4, cy - 4, anchor="w", text=str(sid),
                               fill="#FFDD44", font=("Consolas", 7))

    # ── Monitöre False Color (UART komutu) ──

    def _cmd_apply_lut_to_monitor(self, lut_name):
        """Firmware'e UART komutu göndererek monitörde false color uygula."""
        uart_cmds = {
            "Heatmap": 'h',
            "Rainbow": 'j',
            "Inverted": 'k',
            "Grayscale": 'l',
        }
        cmd = uart_cmds.get(lut_name)
        if not cmd:
            return

        def task():
            # Canvas'ı da güncelle
            self.root.after(0, lambda: self._apply_lut_to_canvas(lut_name))

            self._log_append(f"\n[False Color] {lut_name} uygulanıyor...\n")
            self.root.after(0, lambda: self.status_text.set(
                f"False Color: {lut_name} uygulanıyor..."))

            resp = self._send(cmd, wait=15)
            self._log_append(resp)

            if 'uygulandi' in resp or 'OK' in resp:
                self.root.after(0, lambda: self.status_text.set(
                    f"Monitorde: {lut_name}"))
            else:
                self.root.after(0, lambda: self.status_text.set(
                    f"False Color: {lut_name}"))

        self._run(task)

    # ── Yıldız Haritası ──

    def _draw_star_map(self, results_text):
        """UART sonuçlarından yıldızları parse edip canvas'a çiz."""
        stars = []
        for line in results_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('ID,') or line.startswith('=') or line.startswith('-'):
                continue
            parts = line.split(',')
            if len(parts) == 6:
                try:
                    sid = int(parts[0])
                    x = float(parts[1])
                    y = float(parts[2])
                    brightness = int(parts[3])
                    pixels = int(parts[4])
                    peak = int(parts[5])
                    stars.append((sid, x, y, brightness, pixels, peak))
                except ValueError:
                    continue

        if not stars:
            return

        self.last_stars = stars

        # Eğer bir LUT aktifse, LUT görüntüsü üzerine overlay çiz
        preview_path = os.path.join(self.script_dir, "starfield_preview.png")
        if os.path.exists(preview_path) and self.current_lut.get() != "Grayscale":
            self._apply_lut_to_canvas()
            return

        canvas = self.star_canvas
        canvas.delete("all")

        cw = canvas.winfo_width() or 380
        ch = canvas.winfo_height() or 200

        # Çözünürlük bilgisi
        res = self.resolution_var.get()
        if '1920' in res or '1080' in res:
            img_w, img_h = 1920, 1080
        elif '1280' in res:
            img_w, img_h = 1280, 720 if '720' in res else 1024
        elif '800' in res:
            img_w, img_h = 800, 600
        else:
            img_w, img_h = 640, 480

        sx = cw / img_w
        sy = ch / img_h
        scale = min(sx, sy)
        ox = (cw - img_w * scale) / 2
        oy = (ch - img_h * scale) / 2

        # Arka plan çerçevesi
        canvas.create_rectangle(ox, oy, ox + img_w * scale, oy + img_h * scale,
                                outline="#1E3A5F", width=1)

        # Parlaklık aralığını bul
        brights = [s[3] for s in stars]
        min_b = min(brights)
        max_b = max(brights)
        range_b = max_b - min_b if max_b != min_b else 1

        for sid, x, y, brightness, pixels, peak in stars:
            cx = ox + x * scale
            cy = oy + y * scale
            t = (brightness - min_b) / range_b

            # Renk: mavi(düşük) → yeşil(orta) → kırmızı(yüksek)
            if t < 0.5:
                t2 = t * 2
                r = 0
                g = int(255 * t2)
                b = int(255 * (1 - t2))
            else:
                t2 = (t - 0.5) * 2
                r = int(255 * t2)
                g = int(255 * (1 - t2))
                b = 0

            color = f"#{r:02x}{g:02x}{b:02x}"
            radius = max(3, min(8, pixels * 0.4))

            canvas.create_oval(cx - radius, cy - radius,
                               cx + radius, cy + radius,
                               fill=color, outline="white", width=1)
            canvas.create_text(cx, cy - radius - 8, text=str(sid),
                               fill="#AAAAAA", font=("Consolas", 7))

        # Lejant
        lx = ox + 6
        ly = oy + img_h * scale - 18
        for i, (label, col) in enumerate([("Dusuk", "#0000FF"),
                                           ("Orta", "#00FF00"),
                                           ("Yuksek", "#FF0000")]):
            px = lx + i * 70
            canvas.create_oval(px, ly, px + 8, ly + 8, fill=col, outline="white")
            canvas.create_text(px + 14, ly + 4, text=label, anchor="w",
                               fill="#9DB5D8", font=("Segoe UI", 7))

    def _cmd_scale(self):
        def task():
            self._log_append("Frame olcekleme...\n")
            resp = self._send('8', wait=5)
            self._log_append(resp)
            self.root.after(0, lambda: self.status_text.set("Frame olceklendi"))
        self._run(task)

    def _cmd_change_fb(self, cmd, label):
        def task():
            self._log_append(f"{label} framebuffer degistiriliyor...\n")
            resp = self._send(cmd, wait=1)
            self._log_append(resp)
        self._run(task)

    # ── Star Tracker Komutlari ──

    def _cmd_star_tracker_run(self):
        def task():
            self._log_clear()
            self._log_append("=== STAR TRACKER BASLATILIYOR ===\n\n")
            self.root.after(0, lambda: self.status_text.set(
                "Star Tracker calisiyor..."))
            self.root.after(0, lambda: self.btn_star_run.configure(
                state="disabled"))

            resp = self._send_long('9', timeout=90,
                                   end_marker='===== END RESULTS =====')

            # Sonuclardan yildiz sayisini cikart
            if 'Stars detected:' in resp:
                try:
                    n = resp.split('Stars detected:')[1].split('\r')[0].strip()
                    self.root.after(0, lambda: self.stars_detected.set(n))
                    self.root.after(0, lambda: self.status_text.set(
                        f"Star Tracker: {n} yildiz tespit edildi"))
                except:
                    pass
                # Yıldız haritasını çiz
                self.root.after(100, lambda r=resp: self._draw_star_map(r))
            else:
                self.root.after(0, lambda: self.status_text.set(
                    "Star Tracker tamamlandi"))

            self.root.after(0, lambda: self.btn_star_run.configure(
                state="normal"))
        self._run(task)

    def _cmd_generate_starfield(self):
        def task():
            self._log_clear()
            self._log_append("=== SENTETIK YILDIZ ALANI OLUSTURULUYOR ===\n\n")
            self.root.after(0, lambda: self.status_text.set(
                "Yildiz alani olusturuluyor..."))
            resp = self._send_long('g', timeout=30,
                                   end_marker='calistirabilirsiniz')
            self.root.after(0, lambda: self.status_text.set(
                "Yildiz alani hazir - Star Tracker calistirilabilir"))
        self._run(task)

    def _cmd_clear_overlay(self):
        def task():
            self._log_append("Overlay temizleniyor...\n")
            resp = self._send('0', wait=3)
            self._log_append(resp)
            self.root.after(0, lambda: self.stars_detected.set("0"))
            self.root.after(0, lambda: self.status_text.set("Overlay temizlendi"))
        self._run(task)

    def _cmd_threshold_change(self, direction):
        """direction: '+' veya '-' """
        def task():
            # Threshold menusune gir
            self._send('t', wait=0.5)
            # + veya - gonder
            resp = self._send(direction, wait=0.5)
            # Menudan cik
            resp2 = self._send('q', wait=0.5)
            all_resp = resp + resp2
            # Threshold degerini parse et
            if 'Threshold:' in all_resp:
                try:
                    val = all_resp.split('Threshold:')[-1].split('\r')[0].strip()
                    self.root.after(0, lambda: self.threshold_var.set(int(val)))
                except:
                    pass
            self._log_append(f"Threshold: {self.threshold_var.get()}\n")
        self._run(task)

    # ── Log ──

    def _log_append(self, text):
        def do():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", text)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.root.after(0, do)

    def _log_clear(self):
        def do():
            self.log_box.configure(state="normal")
            self.log_box.delete("1.0", "end")
            self.log_box.configure(state="disabled")
        self.root.after(0, do)

    # ── UI ──

    def _build_ui(self):
        BG      = "#0B1D3A"
        BG2     = "#0F2B5B"
        FG      = "#CCDDEE"
        ACCENT  = "#1E90FF"
        GREEN   = "#00E676"
        RED     = "#FF6B6B"
        GOLD    = "#FFD700"
        CYAN    = "#00BFFF"

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG,
                         font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=ACCENT,
                         font=("Segoe UI", 18, "bold"))
        style.configure("Section.TLabel", background=BG, foreground=CYAN,
                         font=("Segoe UI", 11, "bold"))
        style.configure("Status.TLabel", background=BG, foreground=GREEN,
                         font=("Segoe UI", 9))
        style.configure("Info.TLabel", background=BG2, foreground=GOLD,
                         font=("Segoe UI", 11, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=5)
        style.configure("Star.TButton", font=("Segoe UI", 13, "bold"),
                         padding=10)
        style.configure("Res.TButton", font=("Segoe UI", 10), padding=6)
        style.configure("Small.TButton", font=("Segoe UI", 9), padding=4)
        style.configure("TLabelframe", background=BG, foreground=FG)
        style.configure("TLabelframe.Label", background=BG, foreground=CYAN,
                         font=("Segoe UI", 10, "bold"))

        self.all_buttons = []

        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        # ══════════════ HEADER ══════════════
        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 8))

        ttk.Label(header, text="FPGA HDMI + Star Tracker",
                  style="Title.TLabel").pack(side="left")

        right = ttk.Frame(header)
        right.pack(side="right")
        ttk.Label(right, textvariable=self.status_text,
                  style="Status.TLabel").pack(side="right", padx=(8, 0))
        self.btn_connect = ttk.Button(right, text="Baglan",
                                       command=self._toggle_connect)
        self.btn_connect.pack(side="right", padx=4)
        ttk.Entry(right, textvariable=self.com_port, width=6,
                  font=("Segoe UI", 10)).pack(side="right")

        # ══════════════ INFO BAR ══════════════
        info_frame = tk.Frame(main, bg=BG2, padx=10, pady=6)
        info_frame.pack(fill="x", pady=(0, 8))

        tk.Label(info_frame, text="Cozunurluk:", bg=BG2, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Label(info_frame, textvariable=self.resolution_var, bg=BG2, fg=GOLD,
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=(4, 16))

        tk.Label(info_frame, text="Threshold:", bg=BG2, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Label(info_frame, textvariable=self.threshold_var, bg=BG2, fg=GOLD,
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=(4, 16))

        tk.Label(info_frame, text="Yildiz:", bg=BG2, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Label(info_frame, textvariable=self.stars_detected, bg=BG2, fg=GREEN,
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=(4, 0))

        # ══════════════ STAR TRACKER ══════════════
        st_frame = ttk.LabelFrame(main, text="Star Tracker", padding=8)
        st_frame.pack(fill="x", pady=(0, 8))

        st_row1 = ttk.Frame(st_frame)
        st_row1.pack(fill="x", pady=(0, 6))

        btn_gen = ttk.Button(
            st_row1, text="Yildiz Alani Olustur (g)",
            command=self._cmd_generate_starfield)
        btn_gen.pack(side="left", padx=(0, 4))
        self.all_buttons.append(btn_gen)

        self.btn_star_run = ttk.Button(
            st_row1, text="STAR TRACKER CALISTIR (9)",
            style="Star.TButton", command=self._cmd_star_tracker_run)
        self.btn_star_run.pack(side="left", fill="x", expand=True, padx=4)
        self.all_buttons.append(self.btn_star_run)

        btn_clear = ttk.Button(
            st_row1, text="Overlay Temizle (0)",
            command=self._cmd_clear_overlay)
        btn_clear.pack(side="left", padx=4)
        self.all_buttons.append(btn_clear)

        # Threshold kontrol
        st_row2 = ttk.Frame(st_frame)
        st_row2.pack(fill="x")

        ttk.Label(st_row2, text="Threshold:").pack(side="left", padx=(0, 8))

        btn_t_down = ttk.Button(st_row2, text="- 10",
                                command=lambda: self._cmd_threshold_change('-'),
                                width=6)
        btn_t_down.pack(side="left", padx=2)
        self.all_buttons.append(btn_t_down)

        ttk.Label(st_row2, textvariable=self.threshold_var,
                  font=("Segoe UI", 14, "bold"),
                  foreground=GOLD).pack(side="left", padx=8)

        btn_t_up = ttk.Button(st_row2, text="+ 10",
                              command=lambda: self._cmd_threshold_change('+'),
                              width=6)
        btn_t_up.pack(side="left", padx=2)
        self.all_buttons.append(btn_t_up)

        # ══════════════ YILDIZ HARİTASI + FALSE COLOR ══════════════
        map_frame = ttk.LabelFrame(main, text="Yildiz Haritasi / False Color", padding=4)
        map_frame.pack(fill="x", pady=(0, 8))

        # LUT önizleme butonları
        lut_row1 = ttk.Frame(map_frame)
        lut_row1.pack(fill="x", pady=(0, 2))

        ttk.Label(lut_row1, text="Onizleme:",
                  style="Section.TLabel").pack(side="left", padx=(0, 8))

        for lut_name in ["Grayscale", "Heatmap", "Rainbow", "Inverted"]:
            btn = ttk.Button(lut_row1, text=lut_name, style="Small.TButton",
                             command=lambda n=lut_name: self._apply_lut_to_canvas(n))
            btn.pack(side="left", padx=2)
            self.all_buttons.append(btn)

        # Monitöre yansıtma butonları
        lut_row2 = ttk.Frame(map_frame)
        lut_row2.pack(fill="x", pady=(2, 4))

        ttk.Label(lut_row2, text="Monitore Yansit:",
                  style="Section.TLabel").pack(side="left", padx=(0, 8))

        for lut_name in ["Grayscale", "Heatmap", "Rainbow", "Inverted"]:
            btn = ttk.Button(lut_row2, text=lut_name, style="Small.TButton",
                             command=lambda n=lut_name: self._cmd_apply_lut_to_monitor(n))
            btn.pack(side="left", padx=2)
            self.all_buttons.append(btn)

        btn_chtest = ttk.Button(lut_row2, text="Kanal Test (x)", style="Small.TButton",
                                command=lambda: self._run(lambda: (
                                    self._log_append("Kanal testi: SOL=byte0, ORTA=byte1, SAG=byte2\n"),
                                    self._send('x', wait=3),
                                    self.root.after(0, lambda: self.status_text.set("Kanal testi aktif"))
                                )))
        btn_chtest.pack(side="left", padx=2)
        self.all_buttons.append(btn_chtest)

        self.star_canvas = tk.Canvas(map_frame, bg="#050a14", height=220,
                                     highlightthickness=0)
        self.star_canvas.pack(fill="x", expand=True)
        self.star_canvas.create_text(190, 110, text="Star Tracker calistirin veya\nrenk haritasi secin...",
                                     fill="#334466", font=("Segoe UI", 10),
                                     justify="center")

        # ══════════════ DISPLAY / VIDEO ══════════════
        dv_frame = ttk.LabelFrame(main, text="Display / Video", padding=8)
        dv_frame.pack(fill="x", pady=(0, 8))

        # Cozunurluk
        ttk.Label(dv_frame, text="Cozunurluk:",
                  style="Section.TLabel").pack(anchor="w")
        res_row = ttk.Frame(dv_frame)
        res_row.pack(fill="x", pady=(2, 6))

        resolutions = [
            ("640x480", "1"), ("800x600", "2"), ("720p", "3"),
            ("1280x1024", "4"), ("1080p", "5"),
        ]
        for i, (text, cmd) in enumerate(resolutions):
            btn = ttk.Button(res_row, text=text, style="Res.TButton",
                             command=lambda c=cmd, t=text: self._cmd_resolution(c, t))
            btn.grid(row=0, column=i, padx=2, pady=2, sticky="ew")
            res_row.columnconfigure(i, weight=1)
            self.all_buttons.append(btn)

        # Video + Goruntu kontrol
        ctrl_row = ttk.Frame(dv_frame)
        ctrl_row.pack(fill="x", pady=(2, 0))

        controls = [
            ("Stream Toggle (5)", self._cmd_stream_toggle),
            ("Blended Pattern (3)", lambda: self._cmd_test_pattern('3')),
            ("Color Bar (4)", lambda: self._cmd_test_pattern('4')),
            ("Olcekle (8)", self._cmd_scale),
            ("Display FB (2)", lambda: self._cmd_change_fb('2', 'Display')),
            ("Video FB (6)", lambda: self._cmd_change_fb('6', 'Video')),
        ]
        for i, (text, cmd) in enumerate(controls):
            btn = ttk.Button(ctrl_row, text=text, style="Small.TButton",
                             command=cmd)
            row = i // 4
            col = i % 4
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="ew")
            ctrl_row.columnconfigure(col, weight=1)
            self.all_buttons.append(btn)

        # ══════════════ LOG ══════════════
        log_frame = ttk.LabelFrame(main, text="UART Log", padding=4)
        log_frame.pack(fill="both", expand=True)

        self.log_box = scrolledtext.ScrolledText(
            log_frame, height=10, bg="#0a0e1a", fg="#9DB5D8",
            insertbackground=FG, font=("Consolas", 9),
            state="disabled", wrap="word",
            selectbackground=ACCENT, selectforeground="white"
        )
        self.log_box.pack(fill="both", expand=True)

        # Log temizle butonu
        btn_log_clear = ttk.Button(log_frame, text="Log Temizle",
                                    style="Small.TButton",
                                    command=self._log_clear)
        btn_log_clear.pack(anchor="e", pady=(4, 0))

        # Baslangicta butonlari devre disi birak
        self._set_buttons_state("disabled")

    def _on_close(self):
        if self.ser:
            try:
                self.ser.close()
            except:
                pass
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    StarTrackerPanel(root)
    root.mainloop()
