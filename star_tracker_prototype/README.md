# Star Tracker Prototype - FPGA MicroBlaze

Nexys Video (Artix-7 XC7A200T) uzerinde yildiz tespiti, centroid hesaplama, gorsel overlay ve false color gorsellestirme.

## Ozellikler

- **Yildiz tespiti:** Threshold + Connected Component (flood fill) + Agirlikli Centroid
- **Sub-piksel dogruluk:** Ortalama 0.097 piksel hata (1080p)
- **%100 precision:** Sifir yanlis pozitif
- **Gorsel overlay:** Daire + arti isareti + ID numarasi (monitorde canli)
- **False Color LUT:** Heatmap, Rainbow, Inverted - FPGA uzerinde gercek zamanli renk haritasi
- **HDMI demo entegrasyonu:** Cozunurluk, test pattern + star tracker
- **GUI kontrol paneli:** Tkinter tabanli, tum komutlar tek arayuzde
- **Parlaklik haritasi:** GUI'de yildiz tespiti sonuclarini renk kodlu gorsellestirme

## Dosyalar

### FPGA Kaynak Kodlari
| Dosya | Aciklama |
|-------|----------|
| `video_demo_startracker.c` | Entegre firmware (HDMI demo + star tracker + false color LUT) |
| `star_tracker_integrated.elf` | Derlenmis firmware (FPGA'ya yuklenecek) |
| `star_centroid_standalone.c` | Standalone star tracker (BSP'siz bare-metal) |
| `star_centroid.c` | Star tracker algoritma kaynak kodu |
| `crt0.S` | MicroBlaze assembly startup |
| `lscript.ld` | Linker script (standalone icin) |

### Python Araclari
| Dosya | Aciklama |
|-------|----------|
| `control_panel.py` | GUI kontrol paneli (HDMI + Star Tracker + False Color) |
| `generate_starfield.py` | Sentetik yildiz alani ureteci (1080p) |
| `verify_centroids.py` | Centroid dogrulama + gorsellestirme |
| `run_v2.py` | 1080p otomatik FPGA yukleme + star tracker |
| `run_star_tracker.py` | Tek tikla FPGA programlama (640x480) |

### Otomasyon / Build
| Dosya | Aciklama |
|-------|----------|
| `load_integrated.tcl` | XSDB ile FPGA'ya bitstream + ELF yukleme |
| `load_starfield_xsdb.tcl` | DDR3'e test goruntusu yukleme |
| `build_firmware.bat` | Firmware derleme scripti (Windows) |

## Hizli Baslangic

### Gereksinimler
- AMD/Xilinx Vivado 2025.2 (`C:\AMDDesignTools\2025.2\`)
- Python 3 + pyserial, numpy, Pillow
- Nexys Video FPGA karti (JTAG + HDMI + USB-UART bagli)
- `hdmi_wrapper.bit` dosyasi `C:\temp_fpga\` altinda

### Kurulum ve Calistirma

```bash
# 1. Dosyalari hazirla
mkdir C:\temp_fpga
copy star_tracker_integrated.elf C:\temp_fpga\
# hdmi_wrapper.bit dosyasini C:\temp_fpga\ altina koyun

# 2. Starfield goruntulerini olustur (ilk seferde)
python generate_starfield.py

# 3. FPGA'ya firmware yukle
C:\AMDDesignTools\2025.2\Vivado\bin\xsdb.bat load_integrated.tcl

# 4. Kontrol panelini ac
python control_panel.py

# 5. Panel uzerinden:
#    - COM3'ten Baglan
#    - Yildiz Alani Olustur (g)
#    - STAR TRACKER CALISTIR (9)
#    - False Color: Heatmap / Rainbow / Inverted secenekleri
```

### Alternatif: Otomatik 1080p Test
```bash
python run_v2.py    # FPGA yukle + 1080p + star tracker + UART sonuclari
```

## False Color LUT Modlari

Firmware uzerinde gercek zamanli calisan renk haritalari:

| Mod | UART | Aciklama | Kullanim Alani |
|-----|------|----------|----------------|
| Grayscale | `l` | Orijinal gri tonlama | Referans goruntusu |
| Heatmap | `h` | Siyah-kirmizi-sari-beyaz | Parlaklik analizi, sinyal seviyesi |
| Rainbow | `j` | Mavi-cyan-yesil-sari-kirmizi | Maksimum kontrast, gurultu analizi |
| Inverted | `k` | Ters gri tonlama | Soluk nesne tespiti, baski formati |

- LUT her zaman orijinal grayscale tablosundan hesaplanir (ust uste bozulma yok)
- LUT sonrasi yildiz overlay'leri otomatik yeniden cizilir
- Gercek kanal sirasi: byte0=G, byte1=B, byte2=R (Digilent Nexys Video)

## Derleme

### Entegre Firmware (build_firmware.bat ile)
```bash
build_firmware.bat
```

### Manuel Derleme
```bash
mb-gcc -O2 -mlittle-endian -mno-xl-soft-mul \
  -I<BSP_INCLUDE> -c video_demo_startracker.c -o video_demo.o

mb-gcc -O2 -mlittle-endian -mno-xl-soft-mul \
  -T lscript.ld -L<BSP_LIB> \
  video_demo.o display_ctrl.o video_capture.o dynclk.o intc.o timer_ps.o \
  -lxil -lm -lgcc -o star_tracker_integrated.elf
```

## Sonuclar

| Metrik | 640x480 | 1920x1080 |
|--------|---------|-----------|
| Recall | %88 | %82.5 |
| Precision | %100 | %100 |
| Ort. Centroid Hatasi | 0.093 px | 0.097 px |
| Yanlis Pozitif | 0 | 0 |
| Ground Truth | 40 yildiz | 40 yildiz |
| Tespit Edilen | 35 | 33 |
