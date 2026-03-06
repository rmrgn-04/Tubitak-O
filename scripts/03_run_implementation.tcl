# Vivado 2025.2 - Run Implementation (Place & Route)
# Usage: vivado -mode batch -source scripts/03_run_implementation.tcl

open_project {C:/NexysVideo-HDMI/hw/Nexys-Video-HW/Nexys-Video-HW.xpr}

# Run implementation
launch_runs impl_1 -jobs 4
wait_on_run impl_1

set impl_status [get_property STATUS [get_runs impl_1]]
puts "=== IMPLEMENTATION STATUS: $impl_status ==="

close_project
