"""
Star Tracker - Centroid Dogrulama ve Gorsellestirme
===================================================
UART'tan gelen centroid sonuclarini ground truth ile karsilastirir.

Kullanim:
    1) FPGA'dan UART sonuclarini bir dosyaya kaydet:
       python -m serial.tools.miniterm COM3 115200 > uart_output.txt
       (veya kontrol panelinden kopyala)

    2) Bu script'i calistir:
       python verify_centroids.py

    3) Veya dogrudan COM portunu dinle:
       python verify_centroids.py --live COM3
"""

import csv
import sys
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

def load_ground_truth(path='ground_truth.csv'):
    """Ground truth yildiz konumlarini yukle."""
    stars = []
    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stars.append({
                'id': int(row['star_id']),
                'x': float(row['x_center']),
                'y': float(row['y_center']),
                'brightness': float(row['brightness']),
                'sigma': float(row['sigma'])
            })
    return stars

def parse_uart_output(text):
    """UART ciktisindaki centroid sonuclarini parse et."""
    stars = []
    lines = text.strip().split('\n')
    in_data = False

    for line in lines:
        line = line.strip().replace('\r', '')

        if line.startswith('ID,X,Y,'):
            in_data = True
            continue
        if line.startswith('===== END'):
            in_data = False
            continue

        if in_data and line and line[0].isdigit():
            parts = line.split(',')
            if len(parts) >= 6:
                stars.append({
                    'id': int(parts[0]),
                    'x': float(parts[1]),
                    'y': float(parts[2]),
                    'brightness': float(parts[3]),
                    'pixels': int(parts[4]),
                    'peak': int(parts[5])
                })
    return stars

def match_stars(ground_truth, detected, max_distance=5.0):
    """Ground truth ve tespit edilen yildizlari eslesir (en yakin komsu)."""
    matches = []
    unmatched_gt = list(range(len(ground_truth)))
    unmatched_det = list(range(len(detected)))

    for gi, gt in enumerate(ground_truth):
        best_dist = float('inf')
        best_di = -1

        for di in unmatched_det:
            det = detected[di]
            dist = math.sqrt((gt['x'] - det['x'])**2 + (gt['y'] - det['y'])**2)
            if dist < best_dist:
                best_dist = dist
                best_di = di

        if best_di >= 0 and best_dist < max_distance:
            matches.append({
                'gt_id': gi,
                'det_id': best_di,
                'gt_x': gt['x'],
                'gt_y': gt['y'],
                'det_x': detected[best_di]['x'],
                'det_y': detected[best_di]['y'],
                'error': best_dist
            })
            unmatched_det.remove(best_di)
            unmatched_gt.remove(gi)

    return matches, unmatched_gt, unmatched_det

def create_comparison_image(ground_truth, detected, matches, unmatched_gt, unmatched_det):
    """Karsilastirma gorseli olustur."""
    # Arka plan olarak starfield kulllan
    try:
        bg = Image.open('starfield_preview.png').convert('RGB')
    except FileNotFoundError:
        bg = Image.new('RGB', (640, 480), (10, 10, 30))

    draw = ImageDraw.Draw(bg)

    # Eslesen yildizlar: yesil daire (ground truth) + kirmizi x (detected)
    for m in matches:
        # Ground truth: yesil daire
        r = 10
        draw.ellipse([m['gt_x']-r, m['gt_y']-r, m['gt_x']+r, m['gt_y']+r],
                     outline='lime', width=2)
        # Detected: kirmizi artI
        r2 = 6
        draw.line([m['det_x']-r2, m['det_y'], m['det_x']+r2, m['det_y']],
                  fill='red', width=2)
        draw.line([m['det_x'], m['det_y']-r2, m['det_x'], m['det_y']+r2],
                  fill='red', width=2)
        # Hata cizgisi
        draw.line([m['gt_x'], m['gt_y'], m['det_x'], m['det_y']],
                  fill='yellow', width=1)

    # Eslesmemis ground truth: mavi daire
    for gi in unmatched_gt:
        gt = ground_truth[gi]
        r = 12
        draw.ellipse([gt['x']-r, gt['y']-r, gt['x']+r, gt['y']+r],
                     outline='blue', width=2)

    # Eslesmemis detected: turuncu kare
    for di in unmatched_det:
        det = detected[di]
        r = 8
        draw.rectangle([det['x']-r, det['y']-r, det['x']+r, det['y']+r],
                       outline='orange', width=2)

    # Lejant
    draw.text((10, 10), "Yesil: Ground Truth", fill='lime')
    draw.text((10, 25), "Kirmizi +: FPGA Detected", fill='red')
    draw.text((10, 40), "Sari cizgi: Hata vektoru", fill='yellow')
    draw.text((10, 55), "Mavi: Kacirilmis (missed)", fill='blue')
    draw.text((10, 70), "Turuncu: Fazla tespit (false +)", fill='orange')

    bg.save('centroid_comparison.png')
    print(f"Karsilastirma gorseli: centroid_comparison.png")
    return bg

def print_report(ground_truth, detected, matches, unmatched_gt, unmatched_det):
    """Dogrulama raporu yazdir."""
    print("\n" + "=" * 60)
    print("STAR TRACKER CENTROID DOGRULAMA RAPORU")
    print("=" * 60)
    print(f"Ground Truth yildiz sayisi : {len(ground_truth)}")
    print(f"FPGA tespit edilen sayisi  : {len(detected)}")
    print(f"Basarili esleme            : {len(matches)}")
    print(f"Kacirilmis (missed)        : {len(unmatched_gt)}")
    print(f"Fazla tespit (false pos.)  : {len(unmatched_det)}")
    print()

    if matches:
        errors = [m['error'] for m in matches]
        print(f"Centroid Hata Istatistikleri:")
        print(f"  Ortalama hata : {np.mean(errors):.3f} piksel")
        print(f"  Medyan hata   : {np.median(errors):.3f} piksel")
        print(f"  Max hata      : {np.max(errors):.3f} piksel")
        print(f"  Min hata      : {np.min(errors):.3f} piksel")
        print(f"  Std            : {np.std(errors):.3f} piksel")
        print()

        print(f"{'GT_ID':>5} {'GT_X':>8} {'GT_Y':>8} {'DET_X':>8} {'DET_Y':>8} {'HATA':>8}")
        print("-" * 50)
        for m in sorted(matches, key=lambda x: x['error'], reverse=True):
            print(f"{m['gt_id']:>5} {m['gt_x']:>8.2f} {m['gt_y']:>8.2f} "
                  f"{m['det_x']:>8.2f} {m['det_y']:>8.2f} {m['error']:>8.3f}")

    # Basari orani
    if len(ground_truth) > 0:
        recall = len(matches) / len(ground_truth) * 100
        print(f"\nRecall (tespit orani): {recall:.1f}%")
    if len(detected) > 0:
        precision = len(matches) / len(detected) * 100
        print(f"Precision (dogruluk) : {precision:.1f}%")

    print("=" * 60)

def run_live(port='COM3', baudrate=115200):
    """UART'tan canli dinle."""
    import serial
    print(f"UART dinleniyor: {port} @ {baudrate}...")
    print("FPGA'da star_centroid calistirin. Ctrl+C ile cikis.\n")

    ser = serial.Serial(port, baudrate, timeout=1)
    buffer = ""
    try:
        while True:
            data = ser.read(ser.in_waiting or 1)
            if data:
                text = data.decode('ascii', errors='ignore')
                buffer += text
                sys.stdout.write(text)
                sys.stdout.flush()

                if '===== END RESULTS =====' in buffer:
                    print("\n\nSonuclar alindi! Parse ediliyor...")
                    detected = parse_uart_output(buffer)
                    ground_truth = load_ground_truth()
                    matches, ugt, udet = match_stars(ground_truth, detected)
                    print_report(ground_truth, detected, matches, ugt, udet)
                    create_comparison_image(ground_truth, detected, matches, ugt, udet)
                    buffer = ""
    except KeyboardInterrupt:
        print("\nCikis.")
    finally:
        ser.close()

def run_from_file(filepath):
    """Dosyadan oku ve dogrula."""
    with open(filepath, 'r') as f:
        text = f.read()
    detected = parse_uart_output(text)
    ground_truth = load_ground_truth()
    matches, ugt, udet = match_stars(ground_truth, detected)
    print_report(ground_truth, detected, matches, ugt, udet)
    create_comparison_image(ground_truth, detected, matches, ugt, udet)

def run_simulation():
    """FPGA olmadan Python'da centroid algoritmasi simule et (test amacli)."""
    print("=== SIMULASYON MODU (FPGA olmadan test) ===\n")

    # Goruntu yukle
    try:
        img = np.array(Image.open('starfield_preview.png'))
    except FileNotFoundError:
        print("Hata: Once generate_starfield.py calistirin!")
        return

    THRESHOLD = 50
    height, width = img.shape[:2]

    # Ayni algortimayi Python'da calistir (MicroBlaze C kodunun esdegeri)
    visited = np.zeros((height, width), dtype=bool)
    detected = []

    for row in range(height):
        for col in range(width):
            if img[row, col] > THRESHOLD and not visited[row, col]:
                # Flood fill
                stack = [(col, row)]
                visited[row, col] = True
                sum_x, sum_y, sum_w = 0.0, 0.0, 0.0
                count = 0
                peak = 0

                while stack:
                    cx, cy = stack.pop()
                    val = int(img[cy, cx])
                    weight = val - THRESHOLD
                    sum_x += cx * weight
                    sum_y += cy * weight
                    sum_w += weight
                    count += 1
                    if val > peak:
                        peak = val

                    for dy in range(-1, 2):
                        for dx in range(-1, 2):
                            if dx == 0 and dy == 0:
                                continue
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < width and 0 <= ny < height:
                                if not visited[ny, nx] and img[ny, nx] > THRESHOLD:
                                    visited[ny, nx] = True
                                    stack.append((nx, ny))

                if 3 <= count <= 500 and sum_w > 0:
                    detected.append({
                        'id': len(detected),
                        'x': sum_x / sum_w,
                        'y': sum_y / sum_w,
                        'brightness': sum_w,
                        'pixels': count,
                        'peak': peak
                    })

    print(f"Simule edilen tespit: {len(detected)} yildiz\n")

    # Ground truth ile karsilastir
    ground_truth = load_ground_truth()
    matches, ugt, udet = match_stars(ground_truth, detected)
    print_report(ground_truth, detected, matches, ugt, udet)
    create_comparison_image(ground_truth, detected, matches, ugt, udet)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '--live':
            port = sys.argv[2] if len(sys.argv) > 2 else 'COM3'
            run_live(port)
        elif sys.argv[1] == '--sim':
            run_simulation()
        else:
            run_from_file(sys.argv[1])
    else:
        # Default: simulasyon modu
        run_simulation()
