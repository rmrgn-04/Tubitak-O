# Star Tracker Prototype - FPGA MicroBlaze

Nexys Video (Artix-7 XC7A200T) uzerinde yildiz tespiti, centroid hesaplama ve gorsel overlay.

## Ozellikler

- **Yildiz tespiti:** Threshold + Connected Component (flood fill) + Agirlikli Centroid
- **Sub-piksel dogruluk:** Ortalama 0.097 piksel hata (1080p)
- **%100 precision:** Sifir yanlis pozitif
- **Gorsel overlay:** Yesil daire + kirmizi arti + sari ID numarasi (monitorde canli)
- **HDMI demo entegrasyonu:** Cozunurluk, test pattern, renk inversiyonu + star tracker
- **GUI kontrol paneli:** Tkinter tabanli, tum komutlar tek arayuzde

## Dosyalar

### FPGA Kaynak Kodlari
| Dosya | Aciklama |
|-------|----------|
| `video_demo_startracker.c` | Entegre firmware (HDMI demo + star tracker) |
| `star_centroid_standalone.c` | Standalone star tracker (BSP'siz bare-metal) |
| `crt0.S` | MicroBlaze assembly startup |
| `lscript.ld` | Linker script (standalone icin) |

### Python Araclari
| Dosya | Aciklama |
|-------|----------|
| `control_panel.py` | GUI kontrol paneli (HDMI + Star Tracker) |
| `generate_starfield.py` | Sentetik yildiz alani ureteci |
| `verify_centroids.py` | Centroid dogrulama + gorsellestirme |
| `run_v2.py` | FPGA yukleme otomasyonu |

### XSDB / Otomasyon
| Dosya | Aciklama |
|-------|----------|
| `load_starfield_xsdb.tcl` | DDR3'e test goruntusu yukleme |
| `run_star_tracker.py` | Tek tikla FPGA programlama |

## Hizli Baslangic

### Entegre Firmware (Onerilen)
```bash
# 1. Firmware'i FPGA'ya yukle (XSDB ile)
# 2. Kontrol panelini ac
python control_panel.py
# 3. Baglan -> 1080p -> Yildiz Alani Olustur -> Star Tracker Calistir
```

### Standalone Test
```bash
python generate_starfield.py    # Test goruntusu olustur
python run_v2.py                # FPGA'ya yukle ve calistir
python verify_centroids.py uart_output.txt  # Sonuclari dogrula
```

## Derleme

### Entegre Firmware
```bash
mb-gcc -mlittle-endian -mcpu=v11.0 -O2 \
  video_demo_startracker.c display_ctrl.c video_capture.c dynclk.c intc.c timer_ps.c \
  -I<BSP_INCLUDE> -L<BSP_LIB> -lxil -lm -lgcc -lc -T lscript.ld \
  -o star_tracker_integrated.elf
```

### Standalone
```bash
mb-gcc -mlittle-endian -mcpu=v11.0 -O2 -nostartfiles -nodefaultlibs -fno-builtin \
  crt0.S star_centroid_standalone.c -T lscript.ld <libgcc_path> \
  -o star_centroid.elf
```

## Sonuclar

| Metrik | 640x480 | 1920x1080 |
|--------|---------|-----------|
| Recall | %88 | %82.5 |
| Precision | %100 | %100 |
| Ort. Centroid Hatasi | 0.093 px | 0.097 px |
| Yanlis Pozitif | 0 | 0 |
