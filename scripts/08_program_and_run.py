#!/usr/bin/env python3
"""
FPGA Programlama ve ELF Yukleme Scripti
Bitstream ve ELF dosyalarini Turkce karakter icermeyen bir yola kopyalar,
ardindan Vivado ile programlar ve XSDB ile ELF yukler.

Kullanim:
    python scripts/08_program_and_run.py [vivado_path] [bit_file] [elf_file]
"""
import os
import sys
import shutil
import subprocess
import tempfile

# Varsayilan yollar
VIVADO_DEFAULT = r"C:\AMDDesignTools\2025.2\Vivado\bin\vivado.bat"
XSDB_DEFAULT = r"C:\AMDDesignTools\2025.2\Vivado\bin\xsdb.bat"
BIT_DEFAULT = r"C:\Users\Erim Ergün\NexysVideo-HDMI\hw\Nexys-Video-HW\Nexys-Video-HW.runs\impl_1\hdmi_wrapper.bit"
ELF_DEFAULT = r"C:\Users\Erim Ergün\NexysVideo-HDMI\sw\Nexys-Video-HDMI\Debug\Nexys-Video-HDMI.elf"
SAFE_DIR = r"C:\temp_fpga"

def copy_to_safe_path(src, dest_dir):
    """Dosyayi ASCII-safe yola kopyalar (Turkce karakter sorunu icin)"""
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(src))
    shutil.copy2(src, dest)
    return dest.replace("\\", "/")

def program_bitstream(vivado, bit_path):
    """Vivado ile bitstream yukler"""
    tcl_content = f"""open_hw_manager
connect_hw_server
open_hw_target
set device [lindex [get_hw_devices] 0]
current_hw_device $device
set_property PROGRAM.FILE {{{bit_path}}} $device
program_hw_devices $device
puts "=== BITSTREAM PROGRAMMED ==="
close_hw_manager
"""
    tcl_file = os.path.join(tempfile.gettempdir(), "program_fpga.tcl")
    with open(tcl_file, 'w') as f:
        f.write(tcl_content)

    print("[1/2] Bitstream yukleniyor...")
    result = subprocess.run([vivado, "-mode", "batch", "-source", tcl_file],
                          capture_output=True, text=True, timeout=120)
    if "BITSTREAM PROGRAMMED" in result.stdout:
        print("[OK] Bitstream yuklendi!")
        return True
    else:
        print("[HATA] Bitstream yuklenemedi!")
        print(result.stderr[-500:] if result.stderr else result.stdout[-500:])
        return False

def load_elf(xsdb, elf_path):
    """XSDB ile ELF yukler"""
    tcl_content = f"""connect
after 1000
targets -set -filter {{name =~ "MicroBlaze #0"}}
stop
after 500
dow {{{elf_path}}}
puts "=== ELF DOWNLOADED ==="
con
puts "=== MICROBLAZE RUNNING ==="
after 2000
disconnect
"""
    tcl_file = os.path.join(tempfile.gettempdir(), "load_elf.tcl")
    with open(tcl_file, 'w') as f:
        f.write(tcl_content)

    print("[2/2] ELF yukleniyor...")
    result = subprocess.run([xsdb, tcl_file],
                          capture_output=True, text=True, timeout=60)
    if "ELF DOWNLOADED" in result.stdout:
        print("[OK] ELF yuklendi, MicroBlaze calisiyor!")
        return True
    else:
        print("[HATA] ELF yuklenemedi!")
        print(result.stderr[-500:] if result.stderr else result.stdout[-500:])
        return False

def main():
    vivado = sys.argv[1] if len(sys.argv) > 1 else VIVADO_DEFAULT
    bit_file = sys.argv[2] if len(sys.argv) > 2 else BIT_DEFAULT
    elf_file = sys.argv[3] if len(sys.argv) > 3 else ELF_DEFAULT

    # Turkce karakter kontrolu
    safe_bit = copy_to_safe_path(bit_file, SAFE_DIR)
    safe_elf = copy_to_safe_path(elf_file, SAFE_DIR)
    print(f"Dosyalar {SAFE_DIR} altina kopyalandi")

    xsdb = vivado.replace("vivado.bat", "xsdb.bat")

    if program_bitstream(vivado, safe_bit):
        load_elf(xsdb, safe_elf)
    print("\nTamamlandi. UART kontrolu icin: python scripts/07_uart_check.py")

if __name__ == '__main__':
    main()
