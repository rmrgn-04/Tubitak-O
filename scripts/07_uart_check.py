#!/usr/bin/env python3
"""
FPGA UART Menu Check Script
COM3 uzerinden HDMI Demo menusunu okur ve durumu gosterir.
"""
import serial
import time
import sys

COM_PORT = 'COM3'
BAUD_RATE = 115200
TIMEOUT = 4

def check_uart():
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=TIMEOUT, write_timeout=2)
        ser.reset_input_buffer()
        time.sleep(0.3)
        ser.write(b'\r')
        time.sleep(1.5)
        data = ser.read(4096)
        if data:
            text = data.decode('ascii', errors='replace')
            print(text)
            if '!HDMI UNPLUGGED!' in text:
                print('\n[UYARI] HDMI giris algilanmiyor!')
            elif 'Video Capture Resolution:' in text:
                print('\n[OK] HDMI giris algilandi!')
        else:
            print('[HATA] UART\'tan veri gelmedi')
        ser.close()
        print('\n--- COM3 kapandi ---')
    except serial.SerialException as e:
        print(f'[HATA] COM3 acilamadi: {e}')
        print('Olasi nedenler:')
        print('  - Baska bir program COM3 kullaniyor')
        print('  - Zombi Python process COM3 kilitliyor')
        print('  - USB kablo bagli degil')

if __name__ == '__main__':
    check_uart()
