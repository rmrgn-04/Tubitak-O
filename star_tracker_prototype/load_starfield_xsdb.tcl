# ============================================================
# Star Tracker - XSDB ile DDR3 Framebuffer'a Test Goruntusu Yukleme
# ============================================================
#
# Bu script, generate_starfield.py ile olusturulan raw binary goruntuyu
# FPGA DDR3 bellegine yukler.
#
# Kullanim:
#   xsdb load_starfield_xsdb.tcl
#
# Onkosul:
#   - FPGA bitstream yuklenmis olmali (HDMI demo veya bos MicroBlaze)
#   - DDR3 MIG controller aktif olmali
#   - starfield_640x480.bin dosyasi ayni dizinde olmali
# ============================================================

# Test goruntusu adresi (program kodu 0x80000000'da, cakismasin)
set DDR3_BASE 0x88000000

# Binary dosya yolu (Turkce karakter sorunu icin temp dizine kopyala)
set BIN_FILE "C:/temp_fpga/starfield_640x480.bin"

# Goruntu boyutu
set IMG_WIDTH 640
set IMG_HEIGHT 480
set BPP 4
set FB_SIZE [expr {$IMG_WIDTH * $IMG_HEIGHT * $BPP}]

puts "============================================"
puts "Star Tracker - DDR3 Goruntu Yukleyici"
puts "============================================"
puts "Hedef adres : $DDR3_BASE"
puts "Dosya       : $BIN_FILE"
puts "Boyut       : $FB_SIZE byte ($IMG_WIDTH x $IMG_HEIGHT x $BPP)"
puts ""

# Baglanti kur
puts "JTAG baglantisi kuruluyor..."
connect
after 500

# Hedef secimi (MicroBlaze)
puts "Hedef seciliyor..."
targets -set -filter {name =~ "MicroBlaze*"}

# Islemciyi durdur
puts "MicroBlaze durduruluyor..."
stop
after 200

# Binary dosyayi DDR3'e yaz
puts "Goruntu DDR3'e yukleniyor..."
puts "  Adres: $DDR3_BASE"
puts "  Boyut: $FB_SIZE byte"
mwr -bin -file $BIN_FILE $DDR3_BASE $FB_SIZE
puts "Yukleme tamamlandi!"

# Dogrulama: ilk 16 byte'i oku
puts ""
puts "Dogrulama - Ilk 4 piksel (16 byte):"
set verify_data [mrd $DDR3_BASE 4]
puts $verify_data

puts ""
puts "============================================"
puts "Goruntu basariyla DDR3'e yuklendi!"
puts "Simdi star_centroid.elf yuklenebilir."
puts "============================================"

# Baglanti kapat
disconnect
