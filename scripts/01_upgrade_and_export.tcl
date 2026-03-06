# Vivado 2025.2 - Upgrade project from 2024.1 and export .xsa
# Usage: vivado -mode batch -source scripts/01_upgrade_and_export.tcl

open_project {C:/NexysVideo-HDMI/hw/Nexys-Video-HW/Nexys-Video-HW.xpr}

# Upgrade all IPs to 2025.2 versions
upgrade_ip [get_ips]

# Generate targets for the block design
generate_target all [get_files hdmi.bd]

# Set embedded design intent
set_property platform.design_intent.embedded {true} [current_project]
set_property platform.design_intent.server_managed {false} [current_project]
set_property platform.design_intent.external_host {false} [current_project]
set_property platform.design_intent.datacenter {false} [current_project]

# Export hardware (.xsa)
write_hw_platform -fixed -force {C:/NexysVideo-HDMI/hdmi_wrapper.xsa}

puts "=== XSA EXPORT COMPLETE ==="
close_project
