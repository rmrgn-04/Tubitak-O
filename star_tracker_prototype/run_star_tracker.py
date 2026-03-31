"""
Star Tracker - Tek Tikla Calistirma
====================================
1. Dosyalari ASCII-safe dizine kopyalar (Turkce karakter sorunu)
2. FPGA bitstream yukler
3. Test goruntusunu DDR3'e yazar
4. Star tracker ELF'i MicroBlaze'e yukler
5. UART'tan sonuclari okur

Kullanim:
    python run_star_tracker.py
"""

import os
import sys
import shutil
import subprocess
import time

# --- Ayarlar ---
VIVADO_DIR = r"C:\AMDDesignTools\2025.2\Vivado\bin"
XSDB = os.path.join(VIVADO_DIR, "xsdb.bat")

# Kaynak dosyalar
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BIT_FILE = r"C:\temp_fpga\hdmi_wrapper.bit"
ELF_FILE = os.path.join(SCRIPT_DIR, "star_centroid.elf")
BIN_FILE = os.path.join(SCRIPT_DIR, "starfield_640x480.bin")

# ASCII-safe temp dizin
TEMP_DIR = r"C:\temp_fpga\star_tracker"

# DDR3 adresleri
FB_ADDR = "0x88000000"  # Test goruntusu
FB_SIZE_BYTES = 640 * 480 * 4  # 1,228,800

def copy_to_temp():
    """Dosyalari ASCII-safe dizine kopyala."""
    os.makedirs(TEMP_DIR, exist_ok=True)

    files = {
        "star_centroid.elf": ELF_FILE,
        "starfield_640x480.bin": BIN_FILE,
    }

    # Bitstream zaten temp_fpga'da
    if not os.path.exists(BIT_FILE):
        print(f"HATA: Bitstream bulunamadi: {BIT_FILE}")
        return False

    for name, src in files.items():
        dst = os.path.join(TEMP_DIR, name)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  Kopyalandi: {name}")
        else:
            print(f"  HATA: {src} bulunamadi!")
            return False
    return True

def create_xsdb_script():
    """XSDB script olustur: bitstream + goruntu + ELF yukleme."""
    script = f"""
# Star Tracker - XSDB Yukleme Scripti
puts "============================================"
puts "Star Tracker - FPGA Yukleyici"
puts "============================================"

# 1. Baglanti
puts "\\n[1/5] JTAG baglantisi kuruluyor..."
connect
after 1000

# 2. Bitstream yukle
puts "\\n[2/5] Bitstream yukleniyor..."
fpga -file {{C:/temp_fpga/hdmi_wrapper.bit}}
after 2000
puts "  Bitstream OK"

# 3. MicroBlaze #0'i sec (Debug Module degil, islemcinin kendisi)
puts "\\n[3/5] MicroBlaze hazirlaniyor..."
targets -set -filter {{name =~ "MicroBlaze #0"}}
after 500
stop
after 500
puts "  MicroBlaze #0 durduruldu"

# 4. Test goruntusunu DDR3'e yaz
puts "\\n[4/5] Test goruntusu DDR3'e yukleniyor..."
puts "  Adres: {FB_ADDR}"
puts "  Boyut: {FB_SIZE_BYTES} byte"
mwr -bin -file {{C:/temp_fpga/star_tracker/starfield_640x480.bin}} {FB_ADDR} {FB_SIZE_BYTES}
puts "  Goruntu yuklendi!"

# Dogrulama
puts "  Dogrulama - ilk 4 piksel:"
mrd {FB_ADDR} 4

# 5. Star tracker ELF yukle ve calistir
puts "\\n[5/5] Star Tracker ELF yukleniyor..."
dow {{C:/temp_fpga/star_tracker/star_centroid.elf}}
after 500
puts "  ELF yuklendi, calistiriliyor..."
con
after 8000

puts "\\n============================================"
puts "Star Tracker calisiyor!"
puts "UART ciktisini COM3'ten okuyun (115200 baud)"
puts "============================================"

disconnect
"""
    script_path = os.path.join(TEMP_DIR, "load_all.tcl")
    with open(script_path, 'w') as f:
        f.write(script)
    return script_path

def run_xsdb(script_path):
    """XSDB calistir."""
    print("\nXSDB calistiriliyor...")
    result = subprocess.run(
        [XSDB, script_path],
        capture_output=True, text=True, timeout=120
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    return result.returncode == 0

def read_uart_results(port='COM3', baudrate=115200, timeout_sec=15):
    """UART'tan sonuclari oku."""
    try:
        import serial
    except ImportError:
        print("pyserial yuklu degil! Sonuclari manuel olarak COM3'ten okuyun.")
        return None

    print(f"\nUART dinleniyor ({port} @ {baudrate})...")
    print("Star Tracker sonuclari bekleniyor...\n")

    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        buffer = ""
        start = time.time()

        while time.time() - start < timeout_sec:
            data = ser.read(ser.in_waiting or 1)
            if data:
                text = data.decode('ascii', errors='ignore')
                buffer += text
                sys.stdout.write(text)
                sys.stdout.flush()

                if '===== END RESULTS =====' in buffer:
                    ser.close()
                    return buffer

        ser.close()
        if buffer:
            print(f"\n\nTimeout ({timeout_sec}s). Alinan veri:\n{buffer}")
        else:
            print(f"\nTimeout - UART'tan veri alinamadi.")
        return buffer

    except Exception as e:
        print(f"UART hatasi: {e}")
        print("COM3 baska bir program tarafindan kullaniliyor olabilir.")
        return None

def main():
    print("=" * 50)
    print("STAR TRACKER PROTOTYPE - FPGA Yukleyici")
    print("=" * 50)

    # Adim 1: Dosyalari kopyala
    print("\n[Adim 1] Dosyalar hazirlaniyor...")
    if not copy_to_temp():
        print("HATA: Dosya kopyalama basarisiz!")
        return

    # Adim 2: XSDB script olustur
    print("\n[Adim 2] XSDB script olusturuluyor...")
    script_path = create_xsdb_script()
    print(f"  Script: {script_path}")

    # Adim 3: UART dinlemeyi XSDB'den ONCE baslat (ayri thread)
    import threading
    uart_buffer = {"data": "", "done": False}

    def uart_listener():
        try:
            import serial
            ser = serial.Serial('COM3', 115200, timeout=1)
            start = time.time()
            while time.time() - start < 60 and not uart_buffer["done"]:
                data = ser.read(ser.in_waiting or 1)
                if data:
                    text = data.decode('ascii', errors='ignore')
                    uart_buffer["data"] += text
                    sys.stdout.write(text)
                    sys.stdout.flush()
                    if '===== END RESULTS =====' in uart_buffer["data"]:
                        uart_buffer["done"] = True
            ser.close()
        except Exception as e:
            print(f"UART thread hatasi: {e}")

    print("\n[Adim 3] UART dinleyici baslatiliyor...")
    uart_thread = threading.Thread(target=uart_listener, daemon=True)
    uart_thread.start()
    time.sleep(1)  # UART acilsin

    # Adim 4: XSDB calistir
    print("\n[Adim 4] FPGA programlaniyor...")
    if not run_xsdb(script_path):
        print("UYARI: XSDB hatasi olabilir, devam ediliyor...")

    # Adim 5: UART sonuclarini bekle
    print("\n[Adim 5] UART sonuclari bekleniyor...")
    uart_thread.join(timeout=30)
    uart_data = uart_buffer["data"] if uart_buffer["data"] else None

    if uart_data and '===== END RESULTS =====' in uart_data:
        # Sonuclari dosyaya kaydet
        output_file = os.path.join(SCRIPT_DIR, "uart_output.txt")
        with open(output_file, 'w') as f:
            f.write(uart_data)
        print(f"\nSonuclar kaydedildi: {output_file}")
        print("Dogrulama icin: python verify_centroids.py uart_output.txt")

    print("\nBitti!")

if __name__ == '__main__':
    main()
