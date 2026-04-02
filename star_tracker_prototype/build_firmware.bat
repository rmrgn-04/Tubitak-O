@echo off
REM Star Tracker Integrated Firmware - Derleme Scripti
REM Gereksinim: AMD/Xilinx Vivado 2025.2 kurulu olmali
REM
REM Kullanim:
REM   1. Bu script'i calistirin
REM   2. Olusturulan star_tracker_integrated.elf dosyasini C:\temp_fpga\ altina kopyalayin
REM   3. load_integrated.tcl ile FPGA'ya yukleyin

set MB_GCC=C:\AMDDesignTools\2025.2\gnu\microblaze\nt\bin\mb-gcc.exe
set BSP=C:\temp_fpga\build_st\bsp
set SRC=C:\temp_fpga\build_st\src
set BUILD=C:\temp_fpga\build_st

echo ============================================
echo  Star Tracker Integrated - Firmware Builder
echo ============================================

echo.
echo [1/2] Derleniyor...
"%MB_GCC%" -O2 -mlittle-endian -mno-xl-soft-mul -I"%BSP%\include" -I"%SRC%" -c "%SRC%\video_demo.c" -o "%BUILD%\video_demo.o"
if errorlevel 1 (
    echo HATA: Derleme basarisiz!
    pause
    exit /b 1
)

echo [2/2] Linkleniyor...
"%MB_GCC%" -O2 -mlittle-endian -mno-xl-soft-mul -T"%SRC%\lscript.ld" -L"%BSP%\lib" "%BUILD%\video_demo.o" "%BUILD%\display_ctrl.o" "%BUILD%\video_capture.o" "%BUILD%\dynclk.o" "%BUILD%\intc.o" "%BUILD%\timer_ps.o" -lxil -lm -lgcc -Wl,-Map,"%BUILD%\star_tracker_integrated.map" -o "%BUILD%\star_tracker_integrated.elf"
if errorlevel 1 (
    echo HATA: Linkleme basarisiz!
    pause
    exit /b 1
)

copy "%BUILD%\star_tracker_integrated.elf" "C:\temp_fpga\star_tracker_integrated.elf" >nul

echo.
echo [OK] star_tracker_integrated.elf olusturuldu!
echo      C:\temp_fpga\star_tracker_integrated.elf
echo.
echo Simdi FPGA'ya yuklemek icin:
echo   xsdb load_integrated.tcl
echo.
pause
