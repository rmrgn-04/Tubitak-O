/*
 * MicroBlaze Startup Code (crt0.S)
 * Reset vector -> stack kurulumu -> BSS temizle -> main()
 */

    .section .vectors.reset, "ax"
    .global _start
    .align 2
_start:
    brai    _boot           /* DDR3'teki _boot'a atla */

    .section .text
    .global _boot
    .align 2
_boot:
    /* Stack pointer (R1) ayarla */
    addik   r1, r0, _stack

    /* R13 (small data) - kullanmiyoruz, sifirla */
    addik   r13, r0, 0

    /* BSS temizle */
    addik   r5, r0, __bss_start
    addik   r6, r0, __bss_end
_bss_loop:
    swi     r0, r5, 0          /* *r5 = 0 (4 byte birden) */
    addik   r5, r5, 4
    cmpu    r7, r5, r6
    bgti    r7, _bss_loop

    /* main() cagir */
    brlid   r15, main
    nop

    /* main() donerse sonsuz dongu */
_hang:
    bri     _hang
