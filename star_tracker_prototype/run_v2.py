"""
Star Tracker v2 - 1080p - UART ve XSDB senkronize
"""
import os, sys, time, threading, subprocess, shutil

TEMP_DIR = r"C:\temp_fpga\star_tracker"
XSDB = r"C:\AMDDesignTools\2025.2\Vivado\bin\xsdb.bat"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# UART global
uart_lines = []
uart_done = False

def set_resolution_1080p():
    """HDMI demo UART menusu ile 1080p'ye gec (4 kez '1' bas)."""
    import serial
    try:
        ser = serial.Serial('COM3', 115200, timeout=2)
        time.sleep(1)
        ser.reset_input_buffer()
        for i in range(4):
            ser.write(b'1')
            time.sleep(2)
            resp = ser.read(ser.in_waiting or 1).decode('ascii', errors='ignore')
            if '1920' in resp:
                print(f"  1080p ayarlandi!")
                ser.close()
                return True
        ser.close()
        print("  Cozunurluk 4x degistirildi (1080p olmali)")
        return True
    except Exception as e:
        print(f"  UART hatasi: {e}")
        return False

def uart_listener():
    """UART'tan star tracker sonuclarini dinle."""
    global uart_done
    import serial
    try:
        ser = serial.Serial('COM3', 115200, timeout=0.5)
        ser.reset_input_buffer()
        start = time.time()
        buf = ""
        while time.time() - start < 120 and not uart_done:
            data = ser.read(ser.in_waiting or 1)
            if data:
                text = data.decode('ascii', errors='ignore')
                buf += text
                sys.stdout.write(text)
                sys.stdout.flush()
                if '===== END RESULTS =====' in buf:
                    uart_done = True
        ser.close()
        uart_lines.append(buf)
    except Exception as e:
        print(f"UART hata: {e}")
        uart_lines.append("")

def run_xsdb(script_path, timeout=120):
    result = subprocess.run([XSDB, script_path], capture_output=True, text=True, timeout=timeout)
    return result

# =============================================
print("=" * 50)
print("STAR TRACKER 1080p - FPGA Yukleyici")
print("=" * 50)

# 1. Dosyalari hazirla
os.makedirs(TEMP_DIR, exist_ok=True)
for f in ["star_centroid.elf", "starfield_1080p.bin"]:
    shutil.copy2(os.path.join(SCRIPT_DIR, f), os.path.join(TEMP_DIR, f))
print("[1] Dosyalar kopyalandi")

# 2. HDMI demo ile video pipeline baslat
print("\n[2] Video pipeline baslatiliyor (HDMI demo)...")
init_tcl = os.path.join(TEMP_DIR, "init_video.tcl")
with open(init_tcl, 'w') as f:
    f.write("""
connect
after 1000
fpga -file {C:/temp_fpga/hdmi_wrapper.bit}
after 3000
targets -set -filter {name =~ "MicroBlaze #0"}
stop
after 500
dow {C:/temp_fpga/Nexys-Video-HDMI.elf}
after 500
con
after 5000
puts "VIDEO_PIPELINE_READY"
disconnect
""")
result = run_xsdb(init_tcl, timeout=60)
if "VIDEO_PIPELINE_READY" in result.stdout:
    print("  Video pipeline hazir (640x480)")
else:
    print("  XSDB cikti:", result.stdout[-200:])
time.sleep(2)

# 3. UART ile 1080p'ye gecir
print("\n[3] Cozunurluk 1080p'ye degistiriliyor...")
set_resolution_1080p()
time.sleep(3)

# 4. MicroBlaze durdur, goruntu yaz, star tracker yukle
print("\n[4] Star tracker yuklenecek...")

load_tcl = os.path.join(TEMP_DIR, "load_star_tracker.tcl")
with open(load_tcl, 'w') as f:
    f.write("""
connect
after 1000
targets -set -filter {name =~ "MicroBlaze #0"}
stop
after 500

puts "GORUNTU_YUKLENIYOR"
mwr -bin -file {C:/temp_fpga/star_tracker/starfield_1080p.bin} 0x80000000 8294400
mwr -bin -file {C:/temp_fpga/star_tracker/starfield_1080p.bin} 0x88000000 8294400
after 3000
puts "GORUNTU_OK"

dow {C:/temp_fpga/star_tracker/star_centroid.elf}
after 1000
con
puts "STAR_TRACKER_STARTED"
after 45000
puts "XSDB_DONE"
disconnect
""")

# 5. UART dinleyiciyi baslat
print("\n[5] UART dinleyici baslatiliyor...")
t = threading.Thread(target=uart_listener, daemon=True)
t.start()
time.sleep(2)

# 6. XSDB ile yukle ve calistir
print("[6] XSDB baslatiliyor...\n")
result = run_xsdb(load_tcl, timeout=180)
print("\n--- XSDB ---")
for line in result.stdout.split('\n'):
    if line.strip() and not line.startswith('***') and not line.startswith('INFO') and not line.startswith('  '):
        print(f"  {line.strip()}")

# 7. UART bekle
print("\n[7] UART sonuclari bekleniyor...")
t.join(timeout=60)

# 8. Sonuclari kaydet
if uart_lines and uart_lines[0]:
    outfile = os.path.join(SCRIPT_DIR, "uart_output.txt")
    with open(outfile, 'w') as f:
        f.write(uart_lines[0])
    total = len(uart_lines[0])
    if '===== END RESULTS =====' in uart_lines[0]:
        print(f"\n[BASARILI] {total} karakter - Star tracker sonuclari alindi!")
    else:
        print(f"\n[UYARI] {total} karakter alindi ama sonuclar eksik")
else:
    print("\n[HATA] UART'tan veri alinamadi")
