"""
Sentetik Yildiz Alani Uretici
=============================
- Bilinen konumlarda Gaussian PSF yildizlari olusturur
- 640x480, 24-bit RGB (her piksel 3 byte) raw binary olarak kaydeder
- XSDB ile DDR3 framebuffer'a yuklenecek
- ground_truth.csv ile centroid dogrulamasi yapilabilir

Kullanim:
    python generate_starfield.py
"""

import numpy as np
import struct
import csv
from PIL import Image

# --- Ayarlar ---
WIDTH = 1920
HEIGHT = 1080
NUM_STARS = 40          # Yildiz sayisi
BG_NOISE_MEAN = 15      # Arka plan gurultu ortalamasi (0-255)
BG_NOISE_STD = 5         # Arka plan gurultu standart sapmasi
MIN_BRIGHTNESS = 120     # En dusuk yildiz parlakligi
MAX_BRIGHTNESS = 255     # En yuksek yildiz parlakligi
MIN_SIGMA = 1.2          # En kucuk yildiz yayilimi (piksel)
MAX_SIGMA = 3.0          # En buyuk yildiz yayilimi (piksel)
SEED = 42                # Tekrarlanabilirlik icin

np.random.seed(SEED)

# --- Goruntu olustur ---
image = np.random.normal(BG_NOISE_MEAN, BG_NOISE_STD, (HEIGHT, WIDTH)).astype(np.float64)

# --- Yildiz konumlari ve parametreleri ---
stars = []
margin = 20  # Kenarlardan uzaklik

for i in range(NUM_STARS):
    cx = np.random.uniform(margin, WIDTH - margin)
    cy = np.random.uniform(margin, HEIGHT - margin)
    brightness = np.random.uniform(MIN_BRIGHTNESS, MAX_BRIGHTNESS)
    sigma = np.random.uniform(MIN_SIGMA, MAX_SIGMA)
    stars.append((cx, cy, brightness, sigma))

# --- Gaussian PSF ile yildizlari ciz ---
y_coords, x_coords = np.mgrid[0:HEIGHT, 0:WIDTH]

for cx, cy, brightness, sigma in stars:
    dist_sq = (x_coords - cx)**2 + (y_coords - cy)**2
    psf = brightness * np.exp(-dist_sq / (2 * sigma**2))
    image += psf

# --- 0-255 araligina kliple ---
image = np.clip(image, 0, 255).astype(np.uint8)

# --- 1) PNG olarak kaydet (gorsel kontrol) ---
img_pil = Image.fromarray(image, mode='L')  # Grayscale
img_pil.save('starfield_preview.png')
print(f"PNG kaydedildi: starfield_preview.png ({WIDTH}x{HEIGHT})")

# --- 2) RGB PNG kaydet (FPGA framebuffer formati gibi) ---
img_rgb = Image.fromarray(np.stack([image, image, image], axis=-1), mode='RGB')
img_rgb.save('starfield_rgb_preview.png')

# --- 3) Raw binary kaydet (24-bit RGB, FPGA framebuffer icin) ---
# Digilent HDMI demo: her piksel 3 byte (R, G, B) veya 4 byte (padding + RGB)
# Genelde VDMA 32-bit aligned: 0x00_RR_GG_BB (4 byte per pixel)
raw_data = bytearray()
for row in range(HEIGHT):
    for col in range(WIDTH):
        val = image[row, col]
        # 32-bit per pixel: 0x00_RR_GG_BB (little-endian: BB GG RR 00)
        raw_data += struct.pack('<I', (val << 16) | (val << 8) | val)

with open('starfield_1080p.bin', 'wb') as f:
    f.write(raw_data)
print(f"Raw binary kaydedildi: starfield_1080p.bin ({len(raw_data)} bytes)")
print(f"  Format: 32-bit per pixel (0x00RRGGBB), little-endian")
print(f"  Boyut: {WIDTH}x{HEIGHT} = {WIDTH*HEIGHT} piksel x 4 byte = {WIDTH*HEIGHT*4} byte")

# --- 4) Ground truth CSV kaydet ---
with open('ground_truth.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['star_id', 'x_center', 'y_center', 'brightness', 'sigma'])
    for i, (cx, cy, brightness, sigma) in enumerate(stars):
        writer.writerow([i, f'{cx:.2f}', f'{cy:.2f}', f'{brightness:.1f}', f'{sigma:.2f}'])

print(f"Ground truth kaydedildi: ground_truth.csv ({NUM_STARS} yildiz)")

# --- 5) Ozet ---
print(f"\n=== Yildiz Listesi ===")
print(f"{'ID':>3} {'X':>8} {'Y':>8} {'Parlaklik':>10} {'Sigma':>6}")
print("-" * 40)
for i, (cx, cy, brightness, sigma) in enumerate(stars):
    print(f"{i:>3} {cx:>8.2f} {cy:>8.2f} {brightness:>10.1f} {sigma:>6.2f}")

# --- 6) Threshold simülasyonu (FPGA'da ne beklemeliyiz) ---
threshold = 50  # FPGA'da kullanacagimiz threshold
binary = (image > threshold).astype(np.uint8) * 255
binary_img = Image.fromarray(binary, mode='L')
binary_img.save('starfield_thresholded.png')
print(f"\nThreshold ({threshold}) uygulanmis goruntu: starfield_thresholded.png")
bright_pixels = np.sum(image > threshold)
print(f"Threshold ustu piksel sayisi: {bright_pixels}")
