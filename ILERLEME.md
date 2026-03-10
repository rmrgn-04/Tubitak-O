# HDMI Passthrough Projesi — İlerleme Raporu

## Amaç
FPGA (Nexys Video) üzerinden Tinkerboard'un HDMI çıkışını yakalayıp monitörde göstermek.

**Bağlantı şeması:**
```
Tinkerboard HDMI OUT → FPGA HDMI IN (J4/Sink) → FPGA HDMI OUT (J6/Source) → Monitör
                                                    ↕
                                              UART (COM3, 115200)
                                              USB ile PC'ye bağlı
```

## Tamamlanan Aşamalar

### 1. Bitstream Üretimi
- Digilent Nexys Video HDMI Demo (2024.1-1) Vivado 2025.2'ye upgrade edildi
- TCL scriptleri ile synthesis, implementation ve bitstream üretildi
- Sonuç: `hdmi_wrapper.bit` başarıyla oluşturuldu

### 2. FPGA Programlama
Vivado Hardware Manager ile bitstream yükleme:
```bash
vivado -mode batch -source scripts/05_program_fpga.tcl
```
**Not:** Script'teki yol Türkçe karakter içeriyorsa hata verir. Çözüm:
```bash
# Dosyaları ASCII-safe yola kopyala
mkdir C:\temp_fpga
copy hdmi_wrapper.bit C:\temp_fpga\
copy Nexys-Video-HDMI.elf C:\temp_fpga\
```

Alternatif programlama (Türkçe karakter sorunu için):
```tcl
# program_fpga_safe.tcl
open_hw_manager
connect_hw_server
open_hw_target
set device [lindex [get_hw_devices] 0]
current_hw_device $device
set_property PROGRAM.FILE {C:/temp_fpga/hdmi_wrapper.bit} $device
program_hw_devices $device
puts "=== BITSTREAM PROGRAMMED ==="
close_hw_manager
```

### 3. ELF Yükleme (MicroBlaze)
XSDB ile MicroBlaze'e ELF indirildi:
```bash
xsdb scripts/06_load_elf.tcl
```

Alternatif (Türkçe karakter sorunu için):
```tcl
# load_elf_safe.tcl
connect
after 1000
targets -set -filter {name =~ "MicroBlaze #0"}
stop
after 500
dow {C:/temp_fpga/Nexys-Video-HDMI.elf}
puts "=== ELF DOWNLOADED ==="
con
puts "=== MICROBLAZE RUNNING ==="
after 2000
disconnect
```

### 4. UART Menüsü — Başarılı
COM3 üzerinden 115200 baud ile bağlantı kuruldu. Menü doğru şekilde geliyor:
```
**************************************************
*             Nexys Video HDMI Demo              *
**************************************************
*Display Resolution:                 640x480@60Hz*
*Display Pixel Clock Freq. (MHz):          25.000*
*Display Frame Index:                           0*
*Video Capture Resolution:       !HDMI UNPLUGGED!*
*Video Frame Index:                             0*
**************************************************

1 - Change Display Resolution
2 - Change Display Framebuffer Index
3 - Print Blended Test Pattern to Display Framebuffer
4 - Print Color Bar Test Pattern to Display Framebuffer
5 - Start/Stop Video stream into Video Framebuffer
6 - Change Video Framebuffer Index
7 - Grab Video Frame and invert colors
8 - Grab Video Frame and scale to Display resolution
q - Quit
```

### 5. HDMI Çıkış (FPGA → Monitör) — Başarılı
- FPGA'nın HDMI OUT portu monitöre bağlı
- Color bar test pattern monitörde görünüyor
- Çözünürlük değiştirme çalışıyor (640x480, 800x600, 720p, 1080p)

## Mevcut Sorun: HDMI Giriş Algılanmıyor

### Belirtiler
- UART menüsünde sürekli `!HDMI UNPLUGGED!` gösteriyor
- Tinkerboard'un HDMI çıkışı doğrudan monitöre takılınca çalışıyor (1080p)
- FPGA'nın HDMI IN portuna (J4) takıldığında sinyal algılanmıyor

### Denenen Çözümler

| # | Deneme | Sonuç |
|---|--------|-------|
| 1 | HDMI kabloyu ters takma | Başarısız |
| 2 | HDMI kabloyu çıkarıp tekrar takma (HPD reset) | Başarısız |
| 3 | Çözünürlük değiştirme (720p) | Denenmedi (terminal erişimi sağlanamadı) |
| 4 | Tinkerboard'a SSH ile bağlanma | Devam ediyor — IP adresi bulunamadı |

### Olası Nedenler

#### 1. DVI vs HDMI Uyumsuzluğu (En Muhtemel)
FPGA'daki `DVI2RGB` IP'si sadece **DVI sinyali** kabul eder. Tinkerboard büyük ihtimalle **HDMI modu** ile çıkış veriyor. HDMI, DVI'dan farklı olarak:
- Audio paketleri içerir
- HDCP şifreleme kullanabilir
- InfoFrame paketleri gönderir

DVI2RGB IP'si bunları algılayamayınca pixel clock lock sağlayamıyor.

**Çözüm:** Tinkerboard'un HDMI çıkışını DVI moduna zorlamak:
```bash
# Tinkerboard'da /boot/config.txt veya /boot/hw_intf.conf dosyasına ekle:
# RK3288 tabanlı Tinkerboard için:
hdmi_drive=1  # DVI modu (2 = HDMI modu)
```
Veya xrandr ile:
```bash
xrandr --output HDMI-1 --set "Broadcast RGB" "Full"
```

#### 2. HDCP Sorunu
Tinkerboard HDCP (High-bandwidth Digital Content Protection) aktif olabilir. DVI2RGB IP'si HDCP desteklemiyor.

**Çözüm:** HDCP'yi devre dışı bırakmak:
```bash
# Tinkerboard'da:
echo 0 > /sys/class/drm/card0-HDMI-A-1/content_protection
```

#### 3. EDID Sorunu
FPGA'nın HDMI sink portu düzgün EDID (Extended Display Identification Data) sağlamıyorsa, Tinkerboard HDMI çıkışını aktif etmeyebilir.

**Çözüm:** Tinkerboard'da EDID kontrolünü devre dışı bırakıp zorla çıkış vermek:
```bash
# /boot/config.txt veya kernel parametresi:
drm_kms_helper.edid_firmware=edid/1920x1080.bin
video=HDMI-A-1:1920x1080@60e  # 'e' = enable (force)
```

#### 4. Çözünürlük Uyumsuzluğu (Düşük İhtimal)
DVI2RGB IP'si belirli çözünürlüklerde lock olmayabilir. Tinkerboard'un çözünürlüğünü 640x480 veya 720p'ye düşürmek yardımcı olabilir.

### Kaynak Kod Analizi — HPD ve Lock Mekanizması

`video_capture.c` dosyasında HPD (Hot Plug Detect) ve lock akışı:

```c
// VideoInitialize() fonksiyonunda:
XGpio_DiscreteWrite(&videoPtr->gpio, 1, 0);  // HPD LOW
XGpio_SetDataDirection(&videoPtr->gpio, 1, 0); // HPD = output
XGpio_SetDataDirection(&videoPtr->gpio, 2, 1); // Locked = input
XGpio_InterruptEnable(&videoPtr->gpio, XGPIO_IR_CH2_MASK);
XGpio_InterruptGlobalEnable(&videoPtr->gpio);
XGpio_DiscreteWrite(&videoPtr->gpio, 1, 1);  // HPD HIGH → HDMI kaynağa "hazırım" sinyali

// GpioIsr() — Locked sinyali değiştiğinde çağrılır:
locked = XGpio_DiscreteRead(GpioPtr, 2);  // DVI2RGB'nin pixel clock lock durumu
if (locked) {
    // VTC başlat, timing algıla
} else {
    // Video durdur, state = DISCONNECTED
}
```

**Sorun:** `locked` sinyali hiç HIGH olmuyor — DVI2RGB IP pixel clock'a lock olamıyor.

## Bilinen Sorunlar

### Zombi Python Process Sorunu
Python ile COM3'e bağlanırken timeout veya hata oluşursa serial port handle düzgün kapanmıyor. Bu durumda:
- Python process öldürülemiyor (I/O wait'te takılı)
- COM3 kilitli kalıyor
- Yeni bağlantı açılamıyor

**Çözümler (sırasıyla dene):**
1. `taskkill /F /IM python.exe`
2. FPGA USB kablosunu çıkar-tak (COM3 sıfırlanır)
3. Bilgisayarı kapat-aç (yeniden başlatma yetmeyebilir)

**Önleme:** Python'da her zaman kısa timeout kullan ve try/finally ile portu kapat:
```python
import serial
try:
    ser = serial.Serial('COM3', 115200, timeout=3, write_timeout=2)
    ser.reset_input_buffer()
    # ... işlemler ...
    ser.close()
except Exception as e:
    print(f'Error: {e}')
```

### Türkçe Karakter Sorunu
Windows kullanıcı adında Türkçe karakter (ü, ö, ş, ç, ğ, ı) varsa:
- Vivado dosya yolu hatası verir
- Python stdout encoding hatası verir

**Çözüm:** Dosyaları `C:\temp_fpga\` gibi ASCII-safe yola kopyala.

## Sonraki Adımlar

### Öncelik 1: Tinkerboard'a Erişim
Tinkerboard'un HDMI ayarlarını değiştirmek için erişim sağlanmalı:

- [ ] **Yöntem A — SSH:** Tinkerboard'u Ethernet ile ağa bağla, IP adresini bul, SSH ile bağlan
- [ ] **Yöntem B — SD Kart:** microSD kartı çıkar, PC'ye tak, `/boot/config.txt` düzenle
- [ ] **Yöntem C — Seri Konsol:** Tinkerboard'un debug UART pinlerine bağlan (GPIO header üzerinde)

### Öncelik 2: DVI Moduna Zorla
Erişim sağlandıktan sonra:
```bash
# /boot/config.txt veya /boot/hw_intf.conf dosyasında:
hdmi_drive=1
```

### Öncelik 3: Farklı HDMI Kaynağı ile Test
Sorunun Tinkerboard'a özgü mü yoksa genel mi olduğunu anlamak için:
- Laptop veya başka bir cihazı FPGA HDMI IN portuna bağla
- Eğer çalışırsa sorun kesin Tinkerboard'un HDMI çıkış modunda

## Ortam Bilgileri

| Bileşen | Detay |
|---|---|
| FPGA Kartı | Digilent Nexys Video (XC7A200T) - Serial: 210276B9FF06B |
| FPGA Araçları | Vivado/Vitis 2025.2 (`C:\AMDDesignTools\2025.2\`) |
| USB-Serial Chip | FTDI VID_0403+PID_6001+AV0KROKTA |
| COM Port | COM3, 115200 baud |
| Tinkerboard | ASUS Tinkerboard (RK3288), 1080p HDMI çıkış |
| PC | Windows 11, Python 3.13, pyserial yüklü |
| Ağ | 10.10.192.0/18 (tedu.edu.tr) |
