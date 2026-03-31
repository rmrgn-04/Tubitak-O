# Star Tracker Prototipi - FPGA Uzerinde Yildiz Tespiti ve Centroid Hesaplama

## Proje Raporu

**Proje:** TUBITAK Uzay - FPGA Star Tracker Prototipi
**Platform:** Digilent Nexys Video (Artix-7 XC7A200T)
**Tarih:** Mart 2026

---

## 1. Giris ve Motivasyon

Star tracker (yildiz takipci), uzay araclarinda yonelim belirleme (attitude determination) icin kullanilan kritik bir alt sistemdir. Kamera ile gokyuzu goruntusunu yakalar, yildizlari tespit eder, bir katalog ile eslestirerek uzay aracinin hangi yone baktigini hesaplar.

Bu proje, TÜBİTAK uzay calismalarinin devami olarak, mevcut FPGA HDMI video passthrough altyapisinin uzerine bir star tracker prototipi gelistirmeyi amaclamistir. Daha once FPGA uzerinde gerceklestirilen video yakalama, cozunurluk kontrolu ve UART haberlesme deneyimleri, bu proje icin temel olusturmustur.

### Hedefler

- FPGA uzerinde gercek zamanli yildiz tespiti (centroid detection)
- Sub-piksel dogrulukta centroid hesaplama
- Monitorde gorsel overlay (tespit edilen yildizlarin isaretlenmesi)
- UART uzerinden sonuc raporlama
- Mevcut HDMI demo firmware ile entegrasyon

---

## 2. Arastirma ve Kaynak Taramasi

### 2.1 Incelenen Projeler

Proje basinda, mevcut acik kaynak star tracker cozumleri arastirildi:

| Proje | Kaynak | Ozellik |
|-------|--------|---------|
| **ESA tetra3** | github.com/esa/tetra3 | Lost-in-space plate solver, 10ms cozum suresi |
| **NASA COTS-Star-Tracker** | github.com/nasa/COTS-Star-Tracker | Ticari kamera tabanli star tracker |
| **UWCubeSat LOST** | github.com/UWCubeSat/lost | Sentetik yildiz alani uretici |

### 2.2 Test Verileri

ESA tetra3 reposu klonlanarak gercek gokyuzu goruntuleri elde edildi:

- `2019-07-29T204726_Alt40_Azi-135_Try1.tiff` - Altitude 40°, 1024x768, 16-bit
- `2019-07-29T204726_Alt60_Azi-135_Try1.tiff` - Altitude 60°, 1024x768, 16-bit

Bu goruntulerde FLIR Blackfly S kamerayla cekilmis gercek yildiz alanlari bulunmaktadir.

### 2.3 tetra3 ile Plate Solving Testi

ESA tetra3 kutuphanesi kullanilarak test goruntuleri uzerinde plate solving yapildi:

| Goruntu | RA | Dec | FOV | Cozum Suresi |
|---------|-----|-----|-----|-------------|
| Alt 40° | 230.67° | 11.03° | 11.43° | 0.45 sn |
| Alt 60° | 240.46° | 28.94° | 11.42° | 0.09 sn |

tetra3'un `get_centroids_from_image` fonksiyonu ile 29 yildiz basariyla tespit edildi. Meteor/uydu izleri otomatik olarak filtrelendi.

---

## 3. Sistem Mimarisi

### 3.1 Donanim

| Bilesen | Detay |
|---------|-------|
| FPGA Karti | Digilent Nexys Video (Artix-7 XC7A200T) |
| Soft Processor | MicroBlaze 11.0 (little-endian) |
| Bellek | DDR3 512 MB (MIG 7 Series 4.2) |
| Video Cikis | RGB2DVI 1.4 IP (HDMI) |
| Haberlesme | AXI Uartlite 2.0 (115200 baud, COM3) |
| Video DMA | AXI VDMA 6.3 (triple framebuffer) |

### 3.2 Bellek Haritasi

```
DDR3 (0x80000000 - 0x9FFFFFFF, 512 MB)
  0x00000000 - 0x00001FFF : Local BRAM (8 KB) - Reset/Exception vectors
  0x80000000 - 0x811FFFFF : Framebuffer x3 (her biri ~6 MB, 1920x1080x3)
  0x84000000 - 0x84FFFFFF : Program kodu + BSS (standalone versiyon)
  0x88000000 - 0x887FFFFF : Test goruntusu (standalone versiyon)

Periferaller:
  0x40600000 : AXI Uartlite (UART)
  0x44A00000 : AXI VDMA
  0x44A10000 : Video Timing Controller
```

### 3.3 Yazilim Akisi

```
Sentetik Yildiz Alani (Python veya FPGA firmware)
        |
        v
DDR3 Framebuffer (1920x1080x3 byte, 24-bit RGB)
        |
        v
MicroBlaze: Grayscale Donusum (R+G+B)/3
        |
        v
MicroBlaze: Threshold Uygula (piksel > threshold?)
        |
        v
MicroBlaze: Connected Component (8-connectivity flood fill)
        |
        v
MicroBlaze: Agirlikli Centroid Hesapla
        |
        v
MicroBlaze: Overlay Ciz (daire + arti + ID) -> Framebuffer'a yaz
        |
        v
VDMA -> RGB2DVI -> HDMI Monitor (gorsel sonuc)
        |
        v
UART -> PC (CSV formatinda centroid koordinatlari)
```

---

## 4. Algoritma Detaylari

### 4.1 Grayscale Donusum

Framebuffer'daki her piksel 24-bit RGB formatindadir (Digilent sirasi: R, B, G). Grayscale donusum basit ortalama ile yapilir:

```
grayscale = (R + G + B) / 3
```

### 4.2 Threshold

Sabit bir esik degeri (varsayilan: 50) ile binary harita olusturulur. Esik degeri UART uzerinden +10/-10 adimlarla degistirilebilir.

### 4.3 Connected Component Labeling

Stack tabanli flood fill algoritmasi ile 8-connectivity komsuluk kullanilarak bagli bilesenler tespit edilir:

- **Minimum piksel filtresi:** 3 piksel (gurultu eliminasyonu)
- **Maksimum piksel filtresi:** 500 piksel (buyuk nesneleri eleme)
- **Stack boyutu:** 8192 eleman

### 4.4 Agirlikli Centroid Hesaplama

Her bagli bilesen icin agirlikli merkez hesaplanir:

```
x_centroid = SUM(x_i * (I_i - threshold)) / SUM(I_i - threshold)
y_centroid = SUM(y_i * (I_i - threshold)) / SUM(I_i - threshold)
```

Bu formul sub-piksel dogruluk saglar. Sabit nokta aritmetigi kullanilarak (x100) float islemleri onlenir.

### 4.5 Overlay Cizim

Tespit edilen her yildiz icin framebuffer'a dogrudan yazilir:

- **Yesil daire** (Midpoint circle algoritmasi, r=16-18, 3px kalinlik)
- **Kirmizi arti (+)** isareti (centroid noktasi, 2px kalinlik)
- **Sari ID numarasi** (3x5 piksel font, 3x buyutulmus)

---

## 5. Gelistirme Sureci

### Asama 1: Python Simulasyonu

Ilk olarak algoritmalar Python'da gelistirildi ve dogrulandi:

- `generate_starfield.py`: Sentetik yildiz alani ureteci (Gaussian PSF)
- `verify_centroids.py`: Ground truth ile centroid karsilastirmasi

**Simulasyon Sonuclari:**
- 25/25 yildiz tespit edildi (%100 recall)
- Ortalama centroid hatasi: 0.031 piksel

### Asama 2: Standalone MicroBlaze Firmware

BSP'siz (bare-metal) bir MicroBlaze firmware yazildi:

- `star_centroid_standalone.c`: Tum algoritmalari iceren tek dosya
- `crt0.S`: Assembly startup kodu (stack pointer kurulumu, BSS temizleme)
- UART register-seviyesinde dogrudan erisim (BSP gerektirmez)
- `mb-gcc` ile derleme (libgcc ile division desteği)

**Karsilasilan Zorluklar ve Cozumler:**

| Sorun | Cozum |
|-------|-------|
| `np.math` deprecated (NumPy uyumsuzlugu) | `import math` ile degistirildi |
| Stack pointer baslatilmamis (crash) | `crt0.S` assembly startup yazildi |
| `_SDA_BASE_` undefined | R13 sifira ayarlandi |
| `-lxil` bulunamadi | BSP'siz standalone derleme, libgcc eklendi |
| Turkce karakter (dosya yolu) | `C:\temp_fpga\` ASCII-safe dizine kopyalama |
| UART verisi kacirilmasi | UART listener thread'i XSDB'den once baslatildi |
| Framebuffer-kod adres cakismasi | Linker script: kod 0x84000000'a tasindi |
| Monitor 640x480 kabul etmemesi | 1080p cozunurluge gecis |

### Asama 3: FPGA Uzerinde Test (640x480)

Ilk basarili FPGA testi 640x480 cozunurlukle yapildi:

- XSDB ile DDR3'e test goruntusu yuklendi
- MicroBlaze firmware calistirildi
- UART uzerinden sonuclar alindi

**Sonuclar (640x480):**
- 22/25 yildiz tespit edildi (%88 recall, %100 precision)
- Ortalama centroid hatasi: 0.093 piksel
- 0 yanlis pozitif

### Asama 4: 1080p Gecis

Monitor uyumlulugu icin tum sistem 1920x1080'e tasindi:

- Sentetik yildiz alani 1080p olarak yeniden uretildi
- MicroBlaze kodunda IMG_WIDTH/HEIGHT guncellendi
- BSS boyutu ~4.3 MB'a yükseldi (grayscale + visited dizileri)
- HDMI demo ile cozunurluk 1080p'ye UART komutuyla degistirildi

**Sonuclar (1080p):**
- 33/40 yildiz tespit edildi (%82.5 recall, %100 precision)
- Ortalama centroid hatasi: 0.097 piksel
- 0 yanlis pozitif

### Asama 5: Gorsel Overlay

MicroBlaze firmware'ine framebuffer cizim fonksiyonlari eklendi:

- Midpoint circle algoritmasi (Bresenham)
- Crosshair cizimi
- 3x5 bitmap font (3x buyutulmus, 0-99 arasi sayi gosterimi)
- 24-bit piksel formati destegi (Digilent R,B,G sirasi)

Monitorde yildizlarin etrafinda yesil daireler, merkezde kirmizi arti, saginda sari ID numarasi gorunur hale geldi.

### Asama 6: HDMI Demo ile Entegrasyon

Digilent HDMI demo firmware'i (`video_demo.c`) ile star tracker kodlari tek bir firmware'de birlestirildi:

**Eklenen Ozellikler:**
- `g` : Sentetik yildiz alani olustur (dogrudan framebuffer'a, XSDB gerekmez)
- `9` : Star Tracker calistir (tespit + overlay)
- `0` : Overlay temizle (color bar pattern'a don)
- `t` : Threshold degistir (+/- 10 adim)

**Mevcut Ozellikler Korundu:**
- Cozunurluk degistirme (640x480 - 1920x1080)
- Video stream baslatma/durdurma
- Test pattern (blended, color bar)
- Renk inversiyonu
- Frame olcekleme
- Framebuffer index degistirme

**Derleme:**
- `mb-gcc` (MicroBlaze GCC 13.3.0) ile derleme
- BSP kutuphaneleri: libxil, libm, libgcc, libc
- Toplam kod boyutu: ~120 KB text, ~23 MB BSS (framebuffer x3 + grayscale/visited dizileri)

### Asama 7: Python Kontrol Paneli

Tkinter tabanli GUI kontrol paneli gelistirildi (`control_panel.py`):

- Dark tema (lacivert arka plan, mavi aksan renkleri)
- COM port baglanti yonetimi
- Bilgi cubugu: cozunurluk, threshold, tespit edilen yildiz sayisi
- Star Tracker bolumu: Yildiz Alani Olustur, Star Tracker Calistir, Overlay Temizle, Threshold +/-
- Display/Video bolumu: 5 cozunurluk, stream toggle, test pattern, renk ters, olcekle, FB degistir
- UART log paneli (canli haberlesme izleme)
- Async threading (GUI donmasi onleme)

---

## 6. Sonuclar

### 6.1 Performans Ozeti

| Metrik | 640x480 | 1920x1080 |
|--------|---------|-----------|
| Tespit edilen yildiz | 22/25 | 33/40 |
| Recall | %88.0 | %82.5 |
| Precision | %100 | %100 |
| Ortalama centroid hatasi | 0.093 px | 0.097 px |
| Medyan centroid hatasi | 0.055 px | 0.064 px |
| Max centroid hatasi | 0.310 px | 0.381 px |
| Yanlis pozitif | 0 | 0 |

### 6.2 Sub-Piksel Dogruluk

Agirlikli centroid algoritmasi, her iki cozunurlukde de **0.1 pikselin altinda** ortalama hata ile calismaktadir. Bu, uzay uygulamalarinda tipik olarak istenen 0.1-0.5 piksel dogruluk araliginin icerisindedir.

### 6.3 Sifir Yanlis Pozitif

Her iki testte de **hicbir yanlis pozitif** tespit yapilmamistir. Minimum piksel filtresi (3px) ve threshold kombinasyonu gurultuyu etkili bir sekilde elemektedir.

---

## 7. Dosya Yapisi

```
star_tracker_prototype/
|
|-- Kaynak Kodlar (FPGA)
|   |-- video_demo_startracker.c    Entegre firmware (HDMI demo + star tracker)
|   |-- star_centroid_standalone.c  Standalone star tracker (BSP'siz)
|   |-- star_centroid.c             Standalone (BSP'li referans, kullanilmiyor)
|   |-- crt0.S                      Assembly startup (standalone icin)
|   |-- lscript.ld                  Linker script (standalone icin)
|
|-- Python Araclari
|   |-- control_panel.py            Tkinter GUI kontrol paneli
|   |-- generate_starfield.py       Sentetik yildiz alani ureteci
|   |-- verify_centroids.py         Centroid dogrulama ve gorsellestirme
|   |-- run_v2.py                   FPGA yukleme otomasyon scripti
|
|-- Veri Dosyalari
|   |-- starfield_1080p.bin         1080p raw binary test goruntusu
|   |-- starfield_preview.png       Yildiz alani onizleme (PNG)
|   |-- starfield_thresholded.png   Threshold uygulanmis goruntu
|   |-- ground_truth.csv            Bilinen yildiz konumlari
|   |-- uart_output.txt             FPGA'dan alinan son UART ciktisi
|   |-- centroid_comparison.png     Ground truth vs FPGA karsilastirmasi
|
|-- Dokumantasyon
|   |-- README.md                   Proje aciklamasi ve kullanim kilavuzu
```

---

## 8. Kullanim Kilavuzu

### 8.1 Entegre Firmware (Onerilen)

1. Bitstream + ELF'i FPGA'ya yukleyin:
   ```
   xsdb load_integrated.tcl
   ```

2. Kontrol panelini acin:
   ```
   python control_panel.py
   ```

3. Sirayla: **Baglan** -> **1080p** -> **Yildiz Alani Olustur** -> **Star Tracker Calistir**

### 8.2 Standalone Firmware

1. Sentetik goruntu uretin:
   ```
   python generate_starfield.py
   ```

2. Otomasyon scripti ile calistirin:
   ```
   python run_v2.py
   ```

3. Sonuclari dogrulayin:
   ```
   python verify_centroids.py uart_output.txt
   ```

---

## 9. Gelecek Adimlar

1. **Gercek gokyuzu goruntuleri:** HDMI girisinden kamera baglantisi ile gercek yildiz goruntuleri uzerinde test
2. **Yildiz katalog eslestirme:** Tespit edilen yildiz desenlerini Hipparcos/Tycho katalogu ile eslestirme (plate solving)
3. **Yonelim hesaplama:** QUEST veya TRIAD algoritmasi ile 3 eksen aci hesaplama
4. **Donanim hizlandirma:** Centroid algoritmasini FPGA fabric'ine (AXI4-Stream IP) tasima
5. **FPGA uzerinde CNN:** Yildiz/gurultu ayirimi icin basit sinir agi implementasyonu

---

## 10. Gelistirme Ortami

| Bilesen | Versiyon |
|---------|---------|
| FPGA Araclari | AMD/Xilinx Vivado 2025.2 |
| Derleyici | mb-gcc (MicroBlaze GCC 13.3.0) |
| Python | 3.13 + tkinter + pyserial + numpy + PIL |
| Isletim Sistemi | Windows 11 |
| FPGA Karti | Digilent Nexys Video (S/N: 210276B9FF06B) |
| UART | COM3, 115200 baud (FTDI USB-Serial) |

---

*TUBITAK Uzay Projesi - Mart 2026*
