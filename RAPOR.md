# FPGA HDMI Video Passthrough Projesi — Detaylı Rapor

## 1. Proje Amacı

Bu projenin amacı, bir HDMI video kaynağının (bilgisayar veya Tinkerboard) görüntüsünü Digilent Nexys Video FPGA kartı üzerinden yakalayıp monitöre aktarmak ve bu süreçte kullanıcıya bir kontrol arayüzü sunmaktır. Kontrol arayüzü ile çözünürlük değiştirme, video stream başlatma/durdurma gibi işlemler UART üzerinden gerçekleştirilir.

## 2. Sistem Mimarisi

### 2.1 Donanım

| Bileşen | Model / Detay |
|---|---|
| FPGA Kartı | Digilent Nexys Video (Artix-7 XC7A200T) |
| Soft Processor | MicroBlaze 11.0 |
| Video DMA | AXI VDMA 6.3 |
| HDMI Giriş | DVI2RGB 2.0 IP (DVI sinyal decoder) |
| HDMI Çıkış | RGB2DVI 1.4 IP (DVI sinyal encoder) |
| Bellek | DDR3 - MIG 7 Series 4.2 |
| UART | AXI Uartlite 2.0 (115200 baud, 8N1) |
| Video Zamanlama | Video Timing Controller 6.2 |
| Piksel Clock | AXI Dynamic Clock 1.2 |

### 2.2 Yazılım

| Bileşen | Detay |
|---|---|
| FPGA Araçları | Vivado 2025.2, Vitis 2025.2 |
| Firmware | Digilent HDMI Demo ELF (2024.1-1 release, hazır derlenmiş) |
| Kontrol Paneli | Python 3.13 + tkinter + pyserial |
| İşletim Sistemi | Windows 11 |

### 2.3 Video Akış Yolu

```
HDMI Kaynak → DVI2RGB → AXI4-Stream → VDMA → DDR3 Framebuffer
                                                      ↓
Monitör ← RGB2DVI ← Video Out ← VDMA ← DDR3 Framebuffer
                                                      ↕
                                              MicroBlaze (kontrol)
                                                      ↕
                                              UART ← PC (Python GUI)
```

## 3. Başarıyla Tamamlanan Özellikler

### 3.1 HDMI Video Passthrough

Bilgisayarın HDMI çıkışı FPGA üzerinden monitöre başarıyla aktarıldı. Canlı video stream düzgün çalışıyor, mouse hareketleri ve ekran değişiklikleri gerçek zamanlı olarak monitöre yansıyor.

**Test sonuçları:**
- 1280x720 @ 60Hz: Sorunsuz çalışıyor
- 640x480 @ 60Hz: Çalışıyor
- 800x600 @ 60Hz: Çalışıyor
- 1280x1024 @ 60Hz: Çalışıyor
- 1920x1080 @ 60Hz: Çalışıyor (giriş çözünürlüğü eşleşmeli)

### 3.2 Çözünürlük Kontrolü

UART menüsü üzerinden FPGA çıkış çözünürlüğü başarıyla değiştirilebiliyor. Python kontrol paneli ile kullanıcı dostu arayüz sağlandı. Çözünürlük değişikliği anlık olarak monitöre yansıyor.

### 3.3 FPGA Programlama Otomasyonu

Türkçe karakter sorunu nedeniyle dosya yolları ASCII-safe dizine kopyalanarak Vivado ve XSDB ile otomatik programlama sağlandı (`08_program_and_run.py`).

### 3.4 UART İletişim

COM3 üzerinden 115200 baud ile güvenilir UART iletişimi sağlandı. Python pyserial kütüphanesi ile komut gönderme ve durum okuma başarılı.

## 4. Başarısız Olan Özellikler ve Hata Raporu

### 4.1 Gerçek Zamanlı Renk Çevirme (Başarısız)

**Amaç:** Canlı video stream üzerinde anlık renk inversiyonu.

**Durum:** Firmware'deki menü seçeneği 7 ("Grab Video Frame and invert colors") yalnızca **tek bir frame** yakalar ve yazılımsal olarak piksel piksel ters çevirir.

**Başarısızlık Nedenleri:**
- MicroBlaze soft processor DDR3 bellekteki framebuffer'ı sırayla okuyor ve her pikselin rengini tersleyip geri yazıyor
- 720p çözünürlükte ~921.600 piksel işlenmesi gerekiyor — bu işlem gözle görülür şekilde yavaş (yukarıdan aşağıya doğru yavaşça iniyor)
- İşlem sırasında video stream duruyor, sadece o anki frame işleniyor
- İşlem tamamlandıktan sonra stream otomatik olarak devam etmiyor, ekran donuk kalıyor
- Stream tekrar başlatılsa bile eski ters çevrilmiş frame framebuffer'da kalıyor ve görüntü bozuluyor

**Teknik Sebep:** Renk çevirme donanım (hardware) seviyesinde değil, yazılım (software) seviyesinde yapılıyor. Gerçek zamanlı işlem için VDMA pipeline'ına bir hardware color processing IP'si eklenmesi gerekirdi.

### 4.2 Parlaklık ve Kontrast Kontrolü (Başarısız)

**Amaç:** Monitöre giden görüntünün parlaklık ve kontrastını ayarlamak.

**Durum:** FPGA firmware'inde parlaklık/kontrast ayarı için herhangi bir komut veya IP bulunmuyor.

**Denenen Alternatif:** PC'nin HDMI çıkışının gamma ramp'ini Windows API (`SetDeviceGammaRamp`) ile değiştirerek dolaylı yoldan parlaklık/kontrast kontrolü denendi. Teknik olarak çalıştı ancak bu yöntem:
- FPGA üzerinde değil, PC tarafında işlem yapıyor
- Sadece PC'nin HDMI çıkışını etkiliyor (proje amacına tam uymuyor)
- Monitör seçimi ve DC yönetimi karmaşıklığı ekliyordu

**Teknik Sebep:** Digilent'in HDMI demo firmware'i video sinyali üzerinde herhangi bir görüntü işleme (image processing) yapmıyor. Sadece yakalama ve çıkış var. Parlaklık/kontrast için FPGA block design'ına bir video processing IP (örn. custom AXI4-Stream filter) eklenmesi ve MicroBlaze firmware'inin buna göre güncellenmesi gerekirdi.

### 4.3 Renk Filtresi (Kırmızı/Yeşil/Mavi) (Başarısız)

**Amaç:** Video üzerine renk filtresi uygulamak.

**Durum:** Parlaklık/kontrast ile aynı sebeplerden dolayı firmware seviyesinde desteklenmiyor.

**Teknik Sebep:** Hardware seviyesinde renk kanalı çarpanları (RGB multiplier) için FPGA block design'ında ek IP gerekiyor.

### 4.4 Frame Capture ve Geri Bırakma (Kısmen Başarısız)

**Amaç:** Canlı videodan frame yakalayıp incelemek, sonra tekrar canlı videoya dönmek.

**Durum:** Frame yakalama çalışıyor (menü 7 ve 8), ancak:
- Yakalanan frame ekranda donuk kalıyor
- Stream tekrar başlatıldığında eski frame framebuffer'da kalıyor
- Yeni stream eski frame'in üzerine tam yazamıyor (çözünürlük uyumsuzluğunda sol üst köşeye küçük yazıyor)
- Framebuffer index değişiklikleri karmaşıklık ve tutarsızlık yaratıyor

**Teknik Sebep:** VDMA triple-buffering mekanizması var (3 framebuffer). Frame yakalama bir buffer'a yazıyor ama stream farklı bir buffer'a yazabiliyor. Display ve video framebuffer index'leri senkronize edilmezse görüntü bozuluyor. Ayrıca display çözünürlüğü ile capture çözünürlüğü eşleşmezse frame tam ekranı kaplamıyor.

### 4.5 Tinkerboard HDMI Girişi (Başarısız)

**Amaç:** ASUS Tinkerboard'un HDMI çıkışını FPGA üzerinden monitöre aktarmak.

**Durum:** FPGA UART menüsünde sürekli `!HDMI UNPLUGGED!` gösteriyor. Tinkerboard'un HDMI sinyali algılanmıyor.

**Denenen Çözümler:**

| # | Deneme | Sonuç |
|---|--------|-------|
| 1 | HDMI kablo ters takma | Başarısız |
| 2 | HPD reset (kablo çıkar-tak) | Başarısız |
| 3 | Tinkerboard'a SSH (ağ taraması) | Bulunamadı — 16.381 IP tarandı |
| 4 | Tinkerboard'a Ethernet bağlama | SSH servisi kapalı veya ağda yok |
| 5 | xrandr ile DVI modu zorlama | "Configure crtc 0 failed" hatası |
| 6 | xrandr Broadcast RGB ayarı | "BadName" hatası (RK3288 desteklemiyor) |
| 7 | xrandr audio off | "BadName" hatası |
| 8 | Kernel parametresi (video=HDMI-A-1:1280x720@60D) | /boot/extlinux/ dizini yok |
| 9 | /boot/config.txt düzenleme | Raspberry Pi parametreleri, Tinkerboard'da etkisiz |
| 10 | /boot/cmdline.txt düzenleme | Reboot sonrası değişiklik yok |
| 11 | SD kart ile boot config düzenleme | PC'de SD kart okuyucu yok |

**Teknik Sebep:** FPGA'daki **DVI2RGB IP'si sadece DVI sinyali** kabul ediyor. Tinkerboard (RK3288 SoC) HDMI modunda çıkış veriyor. HDMI sinyali DVI'dan farklı olarak audio paketleri, HDCP şifreleme ve InfoFrame paketleri içeriyor. DVI2RGB IP bunları çözemeyince pixel clock'a kilitlenemiyor.

**Kanıt:** Aynı FPGA'ya bilgisayar HDMI çıkışı bağlandığında sorunsuz çalıştı. Bu, FPGA donanımının sağlam olduğunu ve sorunun kaynağa (Tinkerboard) özgü olduğunu kanıtlıyor.

## 5. Ortam Bilgileri

| Bileşen | Detay |
|---|---|
| FPGA Kartı | Digilent Nexys Video (XC7A200T) - Serial: 210276B9FF06B |
| FPGA Araçları | Vivado/Vitis 2025.2 (`C:\AMDDesignTools\2025.2\`) |
| USB-Serial | FTDI VID_0403+PID_6001+AV0KROKTA |
| COM Port | COM3, 115200 baud |
| Tinkerboard | ASUS Tinkerboard (RK3288), Linaro Debian |
| PC | Windows 11, Python 3.13, pyserial |
| Ağ | 10.10.192.0/18 (tedu.edu.tr) |
| Tarih | 11 Mart 2026 |

## 6. Sonuç ve Öneriler

### Başarılı
- HDMI video passthrough (bilgisayar → FPGA → monitör)
- Çözünürlük kontrolü (5 farklı çözünürlük)
- Python GUI kontrol paneli
- FPGA programlama otomasyonu

### Gelecek İyileştirmeler İçin Öneriler
1. **Tinkerboard için:** USB-UART dönüştürücü ile seri konsol bağlantısı veya USB SD kart okuyucu ile boot config düzenleme
2. **Renk işleme için:** FPGA block design'ına custom AXI4-Stream video processing IP eklenmesi
3. **Parlaklık/Kontrast için:** Hardware LUT (Look-Up Table) tabanlı gamma düzeltme IP'si
4. **Frame capture için:** Framebuffer yönetiminin iyileştirilmesi, display/video FB senkronizasyonu
5. **Firmware güncelleme için:** Vitis 2025.2 MicroBlaze SDT uyumsuzluğu çözülene kadar `mb-gcc` ile manuel derleme
