# Vivado 2025.2 - Program FPGA with bitstream
# Usage: vivado -mode batch -source scripts/05_program_fpga.tcl

open_hw_manager
connect_hw_server

# Find and open the target
open_hw_target

# Get the FPGA device
set device [lindex [get_hw_devices] 0]
current_hw_device $device

# Program bitstream
set_property PROGRAM.FILE {C:/NexysVideo-HDMI/hw/Nexys-Video-HW/Nexys-Video-HW.runs/impl_1/hdmi_wrapper.bit} $device
program_hw_devices $device
puts "=== BITSTREAM PROGRAMMED ==="
