# Nexys Video HDMI Demo — Vivado 2025.2 Uyarlaması

Bu repo, Digilent'in **Nexys Video HDMI Demo** projesinin (2024.1-1 release) **Vivado/Vitis 2025.2** ile çalıştırılması sürecini içerir.

## Proje Nedir?

Nexys Video FPGA kartındaki HDMI giriş (Sink) ve HDMI çıkış (Source) portlarını kullanarak video yakalama, işleme ve çıkış yapma işlevlerini gösteren bir demo projesidir. MicroBlaze soft-processor üzerinde çalışır ve UART (115200 baud) üzerinden kontrol edilir.

### Özellikler
- HDMI çıkış çözünürlüğü değiştirme
- 3 frame buffer arasında geçiş
- Test pattern üretimi (renk çubukları)
- HDMI girişinden canlı video yakalama
- Frame inversion ve scaling

## Gereksinimler

| Bileşen | Detay |
|---|---|
| FPGA Kartı | Digilent Nexys Video (Artix-7 XC7A200T) |
| Yazılım | Vivado 2025.2 + Vitis 2025.2 |
| Kablolar | 1× Micro-USB, 2× HDMI |
| Monitör | HDMI destekli ekran |
| Terminal | PuTTY / TeraTerm (115200 baud, 8N1) |

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

### 4. FPGA'yı Programla

```bash
# Bitstream yükle
vivado -mode batch -source scripts/05_program_fpga.tcl

# ELF'i MicroBlaze'e yükle
xsdb scripts/06_load_elf.tcl
```

### 5. UART ile Bağlan

PuTTY veya TeraTerm ile:
- **Port:** COMx (Device Manager'dan bul)
- **Baud Rate:** 115200
- **Data Bits:** 8, Stop Bits: 1, Parity: None

## Script Açıklamaları

| Script | Açıklama |
|---|---|
| `01_upgrade_and_export.tcl` | 2024.1 projesini 2025.2'ye upgrade eder, IP'leri günceller, block design generate eder, .xsa export eder |
| `02_run_synthesis.tcl` | Synthesis çalıştırır (4 paralel iş) |
| `03_run_implementation.tcl` | Place & Route yapar |
| `04_run_bitstream.tcl` | Bitstream (.bit) dosyası üretir |
| `05_program_fpga.tcl` | Vivado Hardware Manager ile FPGA'yı programlar |
| `06_load_elf.tcl` | XSDB ile ELF'i MicroBlaze'e indirir ve çalıştırır |

## Önemli Notlar

### Türkçe Karakter Sorunu
Windows kullanıcı adında Türkçe karakter (ü, ş, ç vb.) varsa Vivado ve Vitis hata verebilir. Projeyi `C:\NexysVideo-HDMI` gibi ASCII-safe bir yola koyun.

### Vitis 2025.2 Uyumsuzluğu
Vitis 2025.2'nin SDT (System Device Tree) oluşturma mekanizması MicroBlaze XSA'ları ile çalışmıyor (bilinen bug). Bu yüzden 2024.1 release'indeki **hazır derlenmiş ELF** dosyası kullanılıyor. Kaynak kod değişikliği gerekirse `mb-gcc` ile manuel derleme yapılabilir.

### ELF DDR'dan Çalışır
Uygulama DDR belleğe (0x80000000) yüklenir, BRAM'e embed edilemez. Bu nedenle:
1. Önce bitstream yüklenir (FPGA programlanır)
2. Sonra ELF, JTAG üzerinden DDR'a indirilir

## Proje Yapısı

```
NexysVideo-HDMI/
├── scripts/                    # Vivado/XSDB TCL scriptleri
│   ├── 01_upgrade_and_export.tcl
│   ├── 02_run_synthesis.tcl
│   ├── 03_run_implementation.tcl
│   ├── 04_run_bitstream.tcl
│   ├── 05_program_fpga.tcl
│   └── 06_load_elf.tcl
├── hw/                         # Vivado donanım projesi (git dışı)
│   └── Nexys-Video-HW/
├── sw/                         # Yazılım projesi + hazır ELF (git dışı)
│   ├── Nexys-Video-HDMI/
│   │   ├── src/                # C kaynak kodları
│   │   └── Debug/
│   │       └── Nexys-Video-HDMI.elf
│   └── hdmi_wrapper/
├── README.md
└── .gitignore
```

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

## Ek Scriptler

| Script | Açıklama |
|---|---|
| `07_uart_check.py` | COM3 üzerinden UART menüsünü okur, HDMI durumunu gösterir |
| `08_program_and_run.py` | Bitstream + ELF'i tek komutla yükler (Türkçe karakter sorununu otomatik çözer) |
| `09_find_tinkerboard.py` | Ağda Tinkerboard'u SSH port taramasıyla bulur |

## İlerleme Raporu

Detaylı ilerleme, karşılaşılan sorunlar ve çözüm önerileri için bkz: [ILERLEME.md](ILERLEME.md)

## Lisans

Orijinal demo Digilent tarafından sağlanmıştır. Bu repo sadece 2025.2 uyarlama scriptlerini içerir.
