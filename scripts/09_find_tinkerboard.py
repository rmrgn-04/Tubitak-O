#!/usr/bin/env python3
"""
Agda Tinkerboard'u Bulma Scripti
Yerel agdaki tum cihazlarda SSH portunu (22) tarar.
Tinkerboard bulununca IP adresini gosterir.

Kullanim:
    python scripts/09_find_tinkerboard.py
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

def get_subnet_ips(local_ip, mask_bits=18):
    """Subnet'teki tum IP'leri dondurur"""
    parts = list(map(int, local_ip.split('.')))
    ip_int = (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]
    mask = (0xFFFFFFFF << (32 - mask_bits)) & 0xFFFFFFFF
    network = ip_int & mask

    ips = []
    host_count = (1 << (32 - mask_bits)) - 2
    for i in range(1, min(host_count + 1, 16384)):  # max 16k hosts
        host_ip = network | i
        ip_str = f"{(host_ip>>24)&0xFF}.{(host_ip>>16)&0xFF}.{(host_ip>>8)&0xFF}.{host_ip&0xFF}"
        if ip_str != local_ip:
            ips.append(ip_str)
    return ips

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
    print(f"SSH portu acik cihazlar araniyor...\n")

    # Once ARP tablosundan bilinen cihazlari tara (hizli)
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
        print("\nTinkerboard'a baglanmak icin:")
        for ip, banner in found:
            print(f"  ssh linaro@{ip}  (varsayilan sifre: linaro)")
            print(f"  ssh root@{ip}")
    else:
        print("\nARP tablosunda SSH cihaz bulunamadi.")
        print("Tam subnet taramasi yapilsin mi? (cok uzun surebilir)")
        ans = input("[e/h]: ").strip().lower()
        if ans == 'e':
            ips = get_subnet_ips(local_ip)
            print(f"\n{len(ips)} IP taranacak, bu birka\u00e7 dakika surebilir...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=200) as ex:
                results = ex.map(check_ssh, ips)
                for r in results:
                    if r:
                        ip, banner = r
                        found.append(r)
                        print(f"  [SSH] {ip} - {banner}")
            if found:
                print(f"\n{len(found)} SSH cihaz bulundu!")
            else:
                print("\nHicbir SSH cihaz bulunamadi. Tinkerboard'da SSH aktif olmayabilir.")

if __name__ == '__main__':
    main()
