# Vivado 2025.2 - Run Synthesis
# Usage: vivado -mode batch -source scripts/02_run_synthesis.tcl

open_project {C:/NexysVideo-HDMI/hw/Nexys-Video-HW/Nexys-Video-HW.xpr}

# Run synthesis
reset_run synth_1
launch_runs synth_1 -jobs 4
wait_on_run synth_1

# Check status
set synth_status [get_property STATUS [get_runs synth_1]]
puts "=== SYNTHESIS STATUS: $synth_status ==="

close_project
