#!/usr/bin/env python3
"""
Agda Raspberry Pi Bulma Scripti
Yerel agdaki Raspberry Pi cihazlarini SSH (port 22) uzerinden tarar.

Kullanim:
    python scripts/09_find_raspberry.py
"""
import socket
import subprocess
import sys
import re
import concurrent.futures


def get_local_ip():
    """PC'nin yerel IP adresini bulur"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


def check_ssh(ip):
    """SSH portunu kontrol eder, aciksa banner dondurur"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect((ip, 22))
        banner = s.recv(256).decode('ascii', errors='replace').strip()
        s.close()
        return (ip, banner)
    except:
        return None


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    local_ip = get_local_ip()
    print(f"PC IP: {local_ip}")
    print("SSH portu acik cihazlar araniyor...\n")

    # ARP tablosundan bilinen cihazlari tara (hizli)
    try:
        arp_out = subprocess.check_output("arp -a", shell=True, text=True)
        arp_ips = re.findall(r'(\d+\.\d+\.\d+\.\d+)', arp_out)
        arp_ips = [ip for ip in arp_ips if not ip.endswith('.255') and ip != local_ip]
    except:
        arp_ips = []

    print(f"ARP tablosunda {len(arp_ips)} cihaz bulundu, SSH taraniyor...")
    found = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
        results = ex.map(check_ssh, arp_ips)
        for r in results:
            if r:
                ip, banner = r
                found.append(r)
                print(f"  [SSH] {ip} - {banner}")

    if found:
        print(f"\n{len(found)} SSH cihaz bulundu!")
        print("\nRaspberry Pi'ye baglanmak icin:")
        for ip, banner in found:
            print(f"  ssh pi@{ip}  (varsayilan sifre: raspberry)")
        print("\n--- Raspberry Pi config.txt Ayarlari ---")
        print("Asagidaki satirlari /boot/config.txt (veya /boot/firmware/config.txt) dosyasina ekleyin:")
        print()
        print("  hdmi_drive=1            # DVI modu (FPGA DVI2RGB IP ile uyumlu)")
        print("  hdmi_force_hotplug=1    # HDMI her zaman aktif")
        print("  hdmi_group=2            # DMT modlari")
        print("  hdmi_mode=82            # 1920x1080 60Hz (veya istenen cozunurluk)")
        print()
        print("Desteklenen cozunurlukler:")
        print("  hdmi_mode=4   -> 640x480 60Hz")
        print("  hdmi_mode=9   -> 800x600 60Hz")
        print("  hdmi_mode=16  -> 1024x768 60Hz")
        print("  hdmi_mode=35  -> 1280x1024 60Hz")
        print("  hdmi_mode=82  -> 1920x1080 60Hz")
        print()
        print("Ayarlari yaptiktan sonra: sudo reboot")
    else:
        print("\nSSH cihaz bulunamadi.")
        print("Raspberry Pi'nin:")
        print("  - Aga bagli oldugundan")
        print("  - SSH'in aktif oldugundan (raspi-config > Interfaces > SSH)")
        print("  - Acik oldugundan emin olun")

        ans = input("\nTam subnet taramasi yapilsin mi? [e/h]: ").strip().lower()
        if ans == 'e':
            parts = list(map(int, local_ip.split('.')))
            # /24 subnet taramasi
            base = f"{parts[0]}.{parts[1]}.{parts[2]}"
            ips = [f"{base}.{i}" for i in range(1, 255) if f"{base}.{i}" != local_ip]
            print(f"\n{len(ips)} IP taranacak...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=100) as ex:
                results = ex.map(check_ssh, ips)
                for r in results:
                    if r:
                        ip, banner = r
                        found.append(r)
                        print(f"  [SSH] {ip} - {banner}")
            if not found:
                print("\nHicbir SSH cihaz bulunamadi.")


if __name__ == '__main__':
    main()
