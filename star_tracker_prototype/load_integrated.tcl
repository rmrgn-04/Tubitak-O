# Star Tracker Integrated - FPGA Yukleme Scripti
# Kullanim: xsdb load_integrated.tcl
#
# Oncelikle dosyalari C:/temp_fpga/ altina kopyalayin:
#   - hdmi_wrapper.bit -> C:/temp_fpga/hdmi_wrapper.bit
#   - star_tracker_integrated.elf -> C:/temp_fpga/star_tracker_integrated.elf

connect
after 1000
fpga -file {C:/temp_fpga/hdmi_wrapper.bit}
after 3000
targets -set -filter {name =~ "MicroBlaze #0"}
stop
after 500
dow {C:/temp_fpga/star_tracker_integrated.elf}
after 1000
con
after 3000
puts "INTEGRATED_FIRMWARE_RUNNING"
disconnect
