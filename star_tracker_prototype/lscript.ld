/*
 * Star Tracker - MicroBlaze Linker Script
 * ========================================
 * Nexys Video (Artix-7 XC7A200T) DDR3 bellek haritasi:
 *
 *   0x00000000 - 0x00001FFF : Local BRAM (8 KB) - reset/exception vectors
 *   0x80000000 - 0x9FFFFFFF : DDR3 (512 MB)
 *     0x80000000 - 0x80FFFFFF : Program kodu + veri + heap + stack (16 MB)
 *     0x88000000 - 0x8812BFFF : Test goruntusu (framebuffer, ~1.2 MB)
 *
 *   Periferaller:
 *     0x40600000 : AXI Uartlite (UART)
 *     0x44A00000 : AXI VDMA
 *     0x44A10000 : Video Timing Controller
 */

_STACK_SIZE = 0x10000;   /* 64 KB stack */
_HEAP_SIZE  = 0x10000;   /* 64 KB heap  */

MEMORY
{
    local_bram (rwx) : ORIGIN = 0x00000000, LENGTH = 0x00002000
    ddr3_mem   (rwx) : ORIGIN = 0x84000000, LENGTH = 0x04000000
}
/* 0x80000000 - 0x83FFFFFF : Framebuffer (VDMA okur, monitorde gorunur)
 * 0x84000000 - 0x84FFFFFF : Program kodu + veri
 * 0x88000000 - 0x8812BFFF : Star tracker test goruntusu */

ENTRY(_start)

SECTIONS
{
    /* Reset ve exception vektorleri - Local BRAM */
    .vectors.reset 0x00000000 : {
        KEEP(*(.vectors.reset))
    } > local_bram

    .vectors.sw_exception 0x00000008 : {
        KEEP(*(.vectors.sw_exception))
    } > local_bram

    .vectors.interrupt 0x00000010 : {
        KEEP(*(.vectors.interrupt))
    } > local_bram

    .vectors.hw_exception 0x00000020 : {
        KEEP(*(.vectors.hw_exception))
    } > local_bram

    /* Program kodu - DDR3 */
    .text : {
        *(.text)
        *(.text.*)
        *(.gnu.linkonce.t.*)
    } > ddr3_mem

    .init : {
        KEEP(*(.init))
    } > ddr3_mem

    .fini : {
        KEEP(*(.fini))
    } > ddr3_mem

    .rodata : {
        *(.rodata)
        *(.rodata.*)
        *(.gnu.linkonce.r.*)
    } > ddr3_mem

    .sdata2 : {
        *(.sdata2)
        *(.sdata2.*)
    } > ddr3_mem

    .data : {
        *(.data)
        *(.data.*)
        *(.gnu.linkonce.d.*)
    } > ddr3_mem

    .sdata : {
        *(.sdata)
        *(.sdata.*)
    } > ddr3_mem

    .sbss (NOLOAD) : {
        *(.sbss)
        *(.sbss.*)
    } > ddr3_mem

    .bss (NOLOAD) : {
        . = ALIGN(4);
        __bss_start = .;
        *(.bss)
        *(.bss.*)
        *(COMMON)
        . = ALIGN(4);
        __bss_end = .;
    } > ddr3_mem

    _end = .;

    .heap (NOLOAD) : {
        . = ALIGN(8);
        _heap_start = .;
        . += _HEAP_SIZE;
        _heap_end = .;
    } > ddr3_mem

    .stack (NOLOAD) : {
        . = ALIGN(8);
        _stack_end = .;
        . += _STACK_SIZE;
        _stack = .;
    } > ddr3_mem
}
