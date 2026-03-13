# Nexys Video HDMI Demo — Vivado 2025.2 Uyarlaması

Bu repo, Digilent'in **Nexys Video HDMI Demo** projesinin (2024.1-1 release) **Vivado/Vitis 2025.2** ile çalıştırılması sürecini içerir.

## Proje Nedir?

Nexys Video FPGA kartındaki HDMI giriş (Sink) ve HDMI çıkış (Source) portlarını kullanarak video yakalama, işleme ve çıkış yapma işlevlerini gösteren bir demo projesidir. MicroBlaze soft-processor üzerinde çalışır ve UART (115200 baud) üzerinden kontrol edilir.

### Özellikler
- HDMI çıkış çözünürlüğü değiştirme (640x480, 800x600, 720p, 1280x1024, 1080p)
- 3 frame buffer arasında geçiş
- Test pattern üretimi (renk çubukları, blend)
- HDMI girişinden canlı video yakalama ve passthrough
- Sürekli ters renk akışı (~1 fps, MicroBlaze limiti)
- Frame scaling
- Tkinter tabanlı GUI kontrol paneli

## Bağlantı Şeması

```
PC HDMI OUT ──→ FPGA J4 (HDMI IN) ──→ FPGA J6 (HDMI OUT) ──→ Monitör
                      │
                      └── USB (JTAG + UART) ──→ PC COM3
```

## Gereksinimler

| Bileşen | Detay |
|---|---|
| FPGA Kartı | Digilent Nexys Video (Artix-7 XC7A200T) |
| Yazılım | Vivado 2025.2 + Vitis 2025.2 |
| Python | Python 3.x + `pyserial` (`pip install pyserial`) |
| Kablolar | 1× Micro-USB, 2× HDMI |
| Monitör | HDMI destekli ekran |
| HDMI Kaynağı | PC (veya Raspberry Pi `hdmi_drive=1` ile) |

## Hızlı Başlangıç

### 1. Dosyaları İndir

GitHub release'den iki dosyayı indir:
```bash
# Donanım projesi
curl -L -o Nexys-Video-HDMI-hw.xpr.zip \
  "https://github.com/Digilent/Nexys-Video/releases/download/HDMI%2F2024.1-1/Nexys-Video-HDMI-hw.xpr.zip"

# Yazılım projesi
curl -L -o Nexys-Video-HDMI-sw.ide.zip \
  "https://github.com/Digilent/Nexys-Video/releases/download/HDMI%2F2024.1-1/Nexys-Video-HDMI-sw.ide.zip"
```

### 2. Çıkar
```bash
unzip Nexys-Video-HDMI-hw.xpr.zip -d hw
unzip Nexys-Video-HDMI-sw.ide.zip -d sw
```

### 3. Vivado'da Projeyi Upgrade Et ve Bitstream Üret

Aşağıdaki scriptleri sırasıyla çalıştır:

```bash
# 1) IP upgrade + block design generate + XSA export
vivado -mode batch -source scripts/01_upgrade_and_export.tcl

# 2) Synthesis
vivado -mode batch -source scripts/02_run_synthesis.tcl

# 3) Implementation
vivado -mode batch -source scripts/03_run_implementation.tcl

# 4) Bitstream
vivado -mode batch -source scripts/04_run_bitstream.tcl
```

### 4. FPGA'yı Programla (Tek Komut)

```bash
python scripts/08_program_and_run.py
```

Bu script bitstream ve ELF'i Türkçe karakter içermeyen `C:\temp_fpga` yoluna kopyalar, ardından FPGA'yı programlar ve MicroBlaze'i başlatır.

Manuel yükleme:
```bash
vivado -mode batch -source scripts/05_program_fpga.tcl
xsdb scripts/06_load_elf.tcl
```

### 5. Kontrol

```bash
# UART durumunu kontrol et
python scripts/07_uart_check.py

# GUI kontrol panelini aç
python scripts/10_control_panel.py
```

## Script Açıklamaları

| Script | Açıklama |
|---|---|
| `01_upgrade_and_export.tcl` | 2024.1 projesini 2025.2'ye upgrade eder, IP'leri günceller, .xsa export eder |
| `02_run_synthesis.tcl` | Synthesis çalıştırır (4 paralel iş) |
| `03_run_implementation.tcl` | Place & Route yapar |
| `04_run_bitstream.tcl` | Bitstream (.bit) dosyası üretir |
| `05_program_fpga.tcl` | Vivado Hardware Manager ile FPGA'yı programlar |
| `06_load_elf.tcl` | XSDB ile ELF'i MicroBlaze'e indirir ve çalıştırır |
| `07_uart_check.py` | COM3 üzerinden UART menüsünü okur, HDMI durumunu gösterir |
| `08_program_and_run.py` | Bitstream + ELF'i tek komutla yükler (Türkçe karakter sorununu otomatik çözer) |
| `09_find_raspberry.py` | Ağda Raspberry Pi'yi SSH port taramasıyla bulur, config.txt ayarlarını gösterir |
| `10_control_panel.py` | Tkinter GUI: çözünürlük, stream, renk çevirme, test pattern kontrolü |
| `11_image_control.py` | Basit Tkinter GUI: stream toggle ve çözünürlük değiştirme |

## Kontrol Paneli (10_control_panel.py)

GUI üzerinden yapılabilecekler:
- **Bağlan/Kes**: COM port bağlantısı
- **Çözünürlük değiştirme**: 640x480, 800x600, 720p, 1280x1024, 1080p
- **Stream başlat/durdur**: Canlı video akışı
- **Renk ters çevir**: Sürekli ters renkli akış (~1 fps) — tekrar tıkla = normal stream'e dön
- **Ölçekleme**: Frame yakala ve çıkış çözünürlüğüne ölçekle
- **Test pattern**: Blend ve color bar desenleri
- **Framebuffer**: Display ve Video framebuffer index değiştirme

## Raspberry Pi Kullanımı

Raspberry Pi'yi HDMI kaynağı olarak kullanmak için `/boot/config.txt` dosyasına ekleyin:

```ini
hdmi_drive=1            # DVI modu (FPGA DVI2RGB IP ile uyumlu)
hdmi_force_hotplug=1    # HDMI her zaman aktif
hdmi_group=2            # DMT modları
hdmi_mode=82            # 1920x1080 60Hz
```

DVI2RGB IP yalnızca DVI sinyali kabul ettiği için `hdmi_drive=1` zorunludur.

## Önemli Notlar

### Türkçe Karakter Sorunu
Windows kullanıcı adında Türkçe karakter (ü, ş, ç vb.) varsa Vivado ve Vitis hata verebilir. `08_program_and_run.py` scripti dosyaları otomatik olarak `C:\temp_fpga` altına kopyalar.

### Vitis 2025.2 Uyumsuzluğu
Vitis 2025.2'nin SDT (System Device Tree) oluşturma mekanizması MicroBlaze XSA'ları ile çalışmıyor (bilinen bug). Bu yüzden 2024.1 release'indeki **hazır derlenmiş ELF** dosyası kullanılıyor.

### ELF DDR'dan Çalışır
Uygulama DDR belleğe (0x80000000) yüklenir. Bu nedenle:
1. Önce bitstream yüklenir (FPGA programlanır)
2. Sonra ELF, JTAG üzerinden DDR'a indirilir

### Framebuffer Uyumu
Ölçekleme veya renk çevirme sonrası görüntü donarsa, Display ve Video framebuffer index'leri uyumsuz kalmış olabilir. Kontrol panelindeki "Yenile" butonu veya `07_uart_check.py` ile durumu kontrol edin.

## Block Design IP'leri

| IP | Açıklama |
|---|---|
| MicroBlaze 11.0 | Soft processor |
| AXI VDMA 6.3 | Video DMA |
| DVI to RGB 2.0 | HDMI giriş decoder |
| RGB to DVI 1.4 | HDMI çıkış encoder |
| AXI Uartlite 2.0 | UART iletişim |
| Video Timing Controller 6.2 | Video zamanlama |
| AXI4-Stream to Video Out 4.0 | Video çıkış |
| Video In to AXI4-Stream 5.0 | Video giriş |
| MIG 7 Series 4.2 | DDR3 bellek controller |
| AXI Dynamic Clock 1.2 | Piksel clock üretimi |

## Kaynaklar

- [Digilent Nexys Video HDMI Demo](https://digilent.com/reference/programmable-logic/nexys-video/demos/hdmi)
- [GitHub Release (HDMI/2024.1-1)](https://github.com/Digilent/Nexys-Video/releases)
- [Nexys Video Reference Manual](https://digilent.com/reference/programmable-logic/nexys-video/reference-manual)

## İlerleme Raporu

Detaylı ilerleme, karşılaşılan sorunlar ve çözüm önerileri için bkz: [ILERLEME.md](ILERLEME.md)

## Lisans

Orijinal demo Digilent tarafından sağlanmıştır. Bu repo sadece 2025.2 uyarlama scriptlerini içerir.
