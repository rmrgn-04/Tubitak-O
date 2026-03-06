# Vivado 2025.2 - Generate Bitstream
# Usage: vivado -mode batch -source scripts/04_run_bitstream.tcl

open_project {C:/NexysVideo-HDMI/hw/Nexys-Video-HW/Nexys-Video-HW.xpr}

# Generate bitstream
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1

set impl_status [get_property STATUS [get_runs impl_1]]
puts "=== BITSTREAM STATUS: $impl_status ==="

# Check if bitstream was generated
set bit_file "C:/NexysVideo-HDMI/hw/Nexys-Video-HW/Nexys-Video-HW.runs/impl_1/hdmi_wrapper.bit"
if {[file exists $bit_file]} {
    puts "=== BITSTREAM FILE: $bit_file ==="
    puts "=== BITSTREAM SIZE: [file size $bit_file] bytes ==="
} else {
    puts "=== ERROR: Bitstream file not found ==="
}

close_project
