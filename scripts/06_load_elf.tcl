# XSDB script - Download ELF to MicroBlaze and run
# Usage: xsdb scripts/06_load_elf.tcl

connect
after 1000

# Select MicroBlaze #0
targets -set -filter {name =~ "MicroBlaze #0"}

# Stop processor
stop
after 500

# Download ELF
dow {C:/NexysVideo-HDMI/sw/Nexys-Video-HDMI/Debug/Nexys-Video-HDMI.elf}
puts "=== ELF DOWNLOADED ==="

# Run
con
puts "=== MICROBLAZE RUNNING ==="

after 2000
disconnect
