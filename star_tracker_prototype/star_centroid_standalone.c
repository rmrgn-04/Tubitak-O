/**
 * Star Tracker Prototype - MicroBlaze Standalone (BSP'siz)
 * ========================================================
 *
 * Bu versiyon Xilinx BSP gerektirmez.
 * UART cikisini dogrudan register seviyesinde yapar.
 *
 * Derleme:
 *   mb-gcc -mlittle-endian -mcpu=v11.0 -O2 -nostartfiles -o star_centroid.elf \
 *          star_centroid_standalone.c -T lscript.ld
 */

/* ===== Tip Tanimlamalari (stdint.h yerine) ===== */
typedef unsigned char      uint8_t;
typedef unsigned short     uint16_t;
typedef unsigned int       uint32_t;
typedef signed int         int32_t;

/* ===== UART Register Tanimlamalari ===== */
/* AXI Uartlite base adresi (hdmi.hwh'den) */
#define UART_BASE       0x40600000

/* AXI Uartlite register offsetleri */
#define UART_RX         (*(volatile uint32_t*)(UART_BASE + 0x00))  /* RX FIFO */
#define UART_TX         (*(volatile uint32_t*)(UART_BASE + 0x04))  /* TX FIFO */
#define UART_STAT       (*(volatile uint32_t*)(UART_BASE + 0x08))  /* Status */
#define UART_CTRL       (*(volatile uint32_t*)(UART_BASE + 0x0C))  /* Control */

/* Status register bitleri */
#define UART_STAT_TX_FULL   (1 << 3)  /* TX FIFO dolu */
#define UART_STAT_RX_VALID  (1 << 0)  /* RX FIFO'da veri var */

/* ===== Goruntu Parametreleri ===== */
#define IMG_WIDTH       1920
#define IMG_HEIGHT      1080
#define WORK_FB_ADDR    0x88000000  /* Test goruntusu DDR3 adresi (okuma) */
#define DISP_FB_ADDR    0x80000000  /* Display framebuffer (monitore cizim) */

/* ===== Algoritma Parametreleri ===== */
#define THRESHOLD       50
#define MAX_STARS       100
#define MIN_STAR_PIXELS 3
#define MAX_STAR_PIXELS 500

/* ===== Veri Yapilari ===== */
typedef struct {
    int32_t x_100;       /* Centroid X * 100 (sabit nokta, 2 ondalik) */
    int32_t y_100;       /* Centroid Y * 100 */
    int32_t brightness;  /* Toplam parlaklik */
    int32_t pixel_count; /* Piksel sayisi */
    uint8_t peak;        /* En parlak piksel */
} Star;

/* ===== Global Degiskenler ===== */
static uint8_t grayscale[IMG_HEIGHT][IMG_WIDTH];
static uint8_t visited[IMG_HEIGHT][IMG_WIDTH];
static Star    detected_stars[MAX_STARS];
static int     num_stars = 0;

/* Flood fill yigini */
#define STACK_SIZE 8192
static uint16_t stack_x[STACK_SIZE];
static uint16_t stack_y[STACK_SIZE];

/* ===== UART Fonksiyonlari ===== */

void uart_putchar(char c)
{
    /* TX FIFO bos olana kadar bekle */
    while (UART_STAT & UART_STAT_TX_FULL);
    UART_TX = (uint32_t)c;
}

void uart_puts(const char *s)
{
    while (*s) {
        if (*s == '\n') uart_putchar('\r');
        uart_putchar(*s++);
    }
}

/* Sayi -> string donusumu (itoa benzeri) */
static char num_buf[16];

char* int_to_str(int32_t val)
{
    int i = 14;
    int negative = 0;
    uint32_t uval;

    num_buf[15] = '\0';

    if (val < 0) {
        negative = 1;
        uval = (uint32_t)(-(val + 1)) + 1;
    } else {
        uval = (uint32_t)val;
    }

    if (uval == 0) {
        num_buf[i--] = '0';
    } else {
        while (uval > 0 && i >= 0) {
            num_buf[i--] = '0' + (char)(uval % 10);
            uval /= 10;
        }
    }
    if (negative) num_buf[i--] = '-';

    return &num_buf[i + 1];
}

/* "123.45" formatinda sabit nokta cikisi (val = gercek_deger * 100) */
void uart_put_fixed(int32_t val_100)
{
    int32_t whole, frac;
    if (val_100 < 0) {
        uart_putchar('-');
        val_100 = -val_100;
    }
    whole = val_100 / 100;
    frac = val_100 % 100;
    uart_puts(int_to_str(whole));
    uart_putchar('.');
    if (frac < 10) uart_putchar('0');
    uart_puts(int_to_str(frac));
}

void uart_put_int(int32_t val)
{
    uart_puts(int_to_str(val));
}

void uart_put_hex(uint32_t val)
{
    const char hex[] = "0123456789ABCDEF";
    int i;
    uart_puts("0x");
    for (i = 28; i >= 0; i -= 4) {
        uart_putchar(hex[(val >> i) & 0xF]);
    }
}

/* ===== Bellek Fonksiyonlari (libc'siz) ===== */

void* my_memset(void *s, int c, uint32_t n)
{
    uint8_t *p = (uint8_t*)s;
    while (n--) *p++ = (uint8_t)c;
    return s;
}

/* ===== Framebuffer Okuma ===== */

void read_framebuffer(void)
{
    volatile uint32_t *fb = (volatile uint32_t *)WORK_FB_ADDR;
    int row, col;

    for (row = 0; row < IMG_HEIGHT; row++) {
        for (col = 0; col < IMG_WIDTH; col++) {
            uint32_t pixel = fb[row * IMG_WIDTH + col];
            /* 0x00RRGGBB -> grayscale (basit ortalama) */
            uint8_t r = (pixel >> 16) & 0xFF;
            uint8_t g = (pixel >> 8)  & 0xFF;
            uint8_t b = pixel & 0xFF;
            grayscale[row][col] = (uint8_t)((((uint32_t)r + g + b)) / 3);
        }
    }
}

/* ===== Yildiz Tespiti ===== */

void flood_fill_centroid(int start_x, int start_y)
{
    /* Sabit nokta aritmetigi (float yerine) */
    /* sum_x ve sum_y: gercek deger * 1 (agirlikli toplam, sonra bolunecek) */
    int32_t sum_xw = 0;  /* SUM(x * weight) */
    int32_t sum_yw = 0;  /* SUM(y * weight) */
    int32_t sum_w  = 0;  /* SUM(weight) */
    int     count  = 0;
    uint8_t peak   = 0;
    int     sp     = 0;

    stack_x[sp] = (uint16_t)start_x;
    stack_y[sp] = (uint16_t)start_y;
    sp++;
    visited[start_y][start_x] = 1;

    while (sp > 0) {
        sp--;
        int cx = stack_x[sp];
        int cy = stack_y[sp];
        uint8_t val = grayscale[cy][cx];
        int32_t weight = (int32_t)val - THRESHOLD;

        sum_xw += (int32_t)cx * weight;
        sum_yw += (int32_t)cy * weight;
        sum_w  += weight;
        count++;

        if (val > peak) peak = val;

        /* 8-connectivity komsuluk */
        int dx, dy;
        for (dy = -1; dy <= 1; dy++) {
            for (dx = -1; dx <= 1; dx++) {
                if (dx == 0 && dy == 0) continue;
                int nx = cx + dx;
                int ny = cy + dy;
                if (nx < 0 || nx >= IMG_WIDTH || ny < 0 || ny >= IMG_HEIGHT)
                    continue;
                if (!visited[ny][nx] && grayscale[ny][nx] > THRESHOLD) {
                    visited[ny][nx] = 1;
                    if (sp < STACK_SIZE) {
                        stack_x[sp] = (uint16_t)nx;
                        stack_y[sp] = (uint16_t)ny;
                        sp++;
                    }
                }
            }
        }
    }

    if (count < MIN_STAR_PIXELS || count > MAX_STAR_PIXELS)
        return;

    if (sum_w > 0 && num_stars < MAX_STARS) {
        /* Centroid: (sum_xw / sum_w) -> sabit nokta * 100 */
        detected_stars[num_stars].x_100 = (int32_t)((sum_xw * 100) / sum_w);
        detected_stars[num_stars].y_100 = (int32_t)((sum_yw * 100) / sum_w);
        detected_stars[num_stars].brightness = sum_w;
        detected_stars[num_stars].pixel_count = count;
        detected_stars[num_stars].peak = peak;
        num_stars++;
    }
}

void detect_stars(void)
{
    int row, col;
    my_memset(visited, 0, sizeof(visited));
    num_stars = 0;

    for (row = 0; row < IMG_HEIGHT; row++) {
        for (col = 0; col < IMG_WIDTH; col++) {
            if (grayscale[row][col] > THRESHOLD && !visited[row][col]) {
                if (num_stars < MAX_STARS) {
                    flood_fill_centroid(col, row);
                }
            }
        }
    }
}

/* ===== Framebuffer Cizim Fonksiyonlari ===== */

/* Tek piksel yaz (display framebuffer'a) */
void draw_pixel(int x, int y, uint32_t color)
{
    if (x < 0 || x >= IMG_WIDTH || y < 0 || y >= IMG_HEIGHT) return;
    volatile uint32_t *fb = (volatile uint32_t *)DISP_FB_ADDR;
    fb[y * IMG_WIDTH + x] = color;
}

/* Daire ciz (Bresenham/Midpoint circle algoritma) */
void draw_circle(int cx, int cy, int r, uint32_t color)
{
    int x = 0;
    int y = r;
    int d = 1 - r;

    while (x <= y) {
        /* 8 simetrik nokta */
        draw_pixel(cx + x, cy + y, color);
        draw_pixel(cx - x, cy + y, color);
        draw_pixel(cx + x, cy - y, color);
        draw_pixel(cx - x, cy - y, color);
        draw_pixel(cx + y, cy + x, color);
        draw_pixel(cx - y, cy + x, color);
        draw_pixel(cx + y, cy - x, color);
        draw_pixel(cx - y, cy - x, color);
        if (d < 0) {
            d += 2 * x + 3;
        } else {
            d += 2 * (x - y) + 5;
            y--;
        }
        x++;
    }
}

/* Arti isareti ciz (centroid noktasi) */
void draw_crosshair(int cx, int cy, int size, uint32_t color)
{
    int i;
    for (i = -size; i <= size; i++) {
        draw_pixel(cx + i, cy, color);  /* yatay cizgi */
        draw_pixel(cx, cy + i, color);  /* dikey cizgi */
    }
}

/* Kucuk sayi yaz (ID etiketi icin, 3x5 piksel font) */
static const uint8_t font3x5[10][5] = {
    {0x7,0x5,0x5,0x5,0x7}, /* 0 */
    {0x2,0x6,0x2,0x2,0x7}, /* 1 */
    {0x7,0x1,0x7,0x4,0x7}, /* 2 */
    {0x7,0x1,0x7,0x1,0x7}, /* 3 */
    {0x5,0x5,0x7,0x1,0x1}, /* 4 */
    {0x7,0x4,0x7,0x1,0x7}, /* 5 */
    {0x7,0x4,0x7,0x5,0x7}, /* 6 */
    {0x7,0x1,0x1,0x1,0x1}, /* 7 */
    {0x7,0x5,0x7,0x5,0x7}, /* 8 */
    {0x7,0x5,0x7,0x1,0x7}, /* 9 */
};

/* Olcek faktoru - 1080p'de okunabilir boyut */
#define FONT_SCALE 3

void draw_number(int x, int y, int num, uint32_t color)
{
    int tens = num / 10;
    int ones = num % 10;
    int dx, dy, sx, sy;

    if (num >= 10) {
        for (dy = 0; dy < 5; dy++) {
            for (dx = 0; dx < 3; dx++) {
                if (font3x5[tens][dy] & (0x4 >> dx)) {
                    for (sy = 0; sy < FONT_SCALE; sy++)
                        for (sx = 0; sx < FONT_SCALE; sx++)
                            draw_pixel(x + dx*FONT_SCALE + sx,
                                       y + dy*FONT_SCALE + sy, color);
                }
            }
        }
        x += 4 * FONT_SCALE;
    }
    for (dy = 0; dy < 5; dy++) {
        for (dx = 0; dx < 3; dx++) {
            if (font3x5[ones][dy] & (0x4 >> dx)) {
                for (sy = 0; sy < FONT_SCALE; sy++)
                    for (sx = 0; sx < FONT_SCALE; sx++)
                        draw_pixel(x + dx*FONT_SCALE + sx,
                                   y + dy*FONT_SCALE + sy, color);
            }
        }
    }
}

/* Tespit edilen yildizlari display framebuffer'a ciz */
void draw_overlays(void)
{
    int i;
    /* Renk tanimlari: 0x00RRGGBB */
    uint32_t RED    = 0x00FF0000;
    uint32_t GREEN  = 0x0000FF00;
    uint32_t CYAN   = 0x0000FFFF;
    uint32_t YELLOW = 0x00FFFF00;

    for (i = 0; i < num_stars; i++) {
        int cx = detected_stars[i].x_100 / 100;
        int cy = detected_stars[i].y_100 / 100;

        /* Dis daire (yesil) - tespit bolgesi, 3 piksel kalin */
        draw_circle(cx, cy, 16, GREEN);
        draw_circle(cx, cy, 17, GREEN);
        draw_circle(cx, cy, 18, GREEN);

        /* Arti isareti (kirmizi) - centroid noktasi */
        draw_crosshair(cx, cy, 6, RED);
        draw_crosshair(cx, cy + 1, 6, RED);  /* 2px kalin */

        /* Yildiz ID numarasi (sari, sag ust) */
        draw_number(cx + 22, cy - 12, i, YELLOW);
    }
}

/* ===== Sonuc Ciktisi ===== */

void send_results(void)
{
    int i;

    uart_puts("\n===== STAR TRACKER RESULTS =====\n");
    uart_puts("Image: 1920x1080, Threshold: ");
    uart_put_int(THRESHOLD);
    uart_puts("\nStars detected: ");
    uart_put_int(num_stars);
    uart_puts("\n--------------------------------\n");
    uart_puts("ID,X,Y,BRIGHTNESS,PIXELS,PEAK\n");

    for (i = 0; i < num_stars; i++) {
        uart_put_int(i);
        uart_putchar(',');
        uart_put_fixed(detected_stars[i].x_100);
        uart_putchar(',');
        uart_put_fixed(detected_stars[i].y_100);
        uart_putchar(',');
        uart_put_int(detected_stars[i].brightness);
        uart_putchar(',');
        uart_put_int(detected_stars[i].pixel_count);
        uart_putchar(',');
        uart_put_int((int32_t)detected_stars[i].peak);
        uart_putchar('\n');
    }

    uart_puts("===== END RESULTS =====\n");
}

/* ===== Ana Fonksiyon ===== */

int main(void)
{
    uart_puts("\n[Star Tracker] Baslatiliyor...\n");
    uart_puts("[Star Tracker] Okuma FB : ");
    uart_put_hex(WORK_FB_ADDR);
    uart_puts("\n[Star Tracker] Display FB: ");
    uart_put_hex(DISP_FB_ADDR);
    uart_puts("\n[Star Tracker] Goruntu: 1920x1080\n");

    /* Adim 1: Framebuffer oku */
    uart_puts("[Star Tracker] Adim 1: Framebuffer okunuyor...\n");
    read_framebuffer();
    uart_puts("[Star Tracker] Adim 1: OK\n");

    /* Adim 2: Yildiz tespiti */
    uart_puts("[Star Tracker] Adim 2: Yildiz tespiti (threshold=");
    uart_put_int(THRESHOLD);
    uart_puts(")...\n");
    detect_stars();
    uart_puts("[Star Tracker] Adim 2: OK - ");
    uart_put_int(num_stars);
    uart_puts(" yildiz bulundu.\n");

    /* Adim 3: Sonuclari monitore ciz */
    uart_puts("[Star Tracker] Adim 3: Overlay ciziliyor...\n");
    draw_overlays();
    uart_puts("[Star Tracker] Adim 3: OK - Monitorde gormelisiniz!\n");

    /* Adim 4: Sonuclari UART'tan gonder */
    send_results();

    uart_puts("[Star Tracker] Bitti.\n");

    /* Sonsuz dongu (MicroBlaze durmasin) */
    while(1);

    return 0;
}

/* Startup kodu crt0.S dosyasinda (assembly) */
