/**
 * Star Tracker Prototype - MicroBlaze Centroid Detection
 * ======================================================
 *
 * DDR3 framebuffer'daki goruntude yildiz tespiti ve centroid hesaplama.
 *
 * Algoritma:
 *   1. Framebuffer'dan pikselleri oku (32-bit: 0x00RRGGBB)
 *   2. Grayscale'e cevir (Green kanali veya ortalama)
 *   3. Threshold uygula -> binary harita
 *   4. Connected component labeling (flood fill)
 *   5. Her component icin agirlikli centroid hesapla
 *   6. Sonuclari UART uzerinden gonder
 *
 * Derleme (Vitis / mb-gcc):
 *   mb-gcc -O2 -o star_centroid.elf star_centroid.c -lm
 *
 * Not: Bu kod Digilent HDMI demo firmware'inden BAGIMSIZ calisir.
 *      XSDB ile DDR3'e test goruntusu yukledikten sonra bu ELF calistirilir.
 */

#include <stdio.h>
#include <stdint.h>
#include <string.h>

/* --- Platform Tanimlamalari --- */
/* Nexys Video DDR3 base adresi (MIG controller) */
#define DDR3_BASE       0x80000000

/* Framebuffer parametreleri */
#define IMG_WIDTH       640
#define IMG_HEIGHT      480
#define BYTES_PER_PIXEL 4       /* 32-bit per pixel: 0x00RRGGBB */
#define FB_STRIDE       (IMG_WIDTH * BYTES_PER_PIXEL)
#define FB_SIZE         (IMG_WIDTH * IMG_HEIGHT * BYTES_PER_PIXEL)

/* Framebuffer adresleri (3 framebuffer, VDMA triple buffering) */
#define FB0_ADDR        DDR3_BASE
#define FB1_ADDR        (DDR3_BASE + FB_SIZE)
#define FB2_ADDR        (DDR3_BASE + 2 * FB_SIZE)

/* Islenecek framebuffer (test goruntusu buraya yuklenecek) */
/* Not: 0x88000000 adresi secildi - program koduyla (0x80000000) cakismasin */
#define WORK_FB_ADDR    0x88000000

/* Algoritma parametreleri */
#define THRESHOLD       50      /* Yildiz parlaklik esigi (0-255) */
#define MAX_STARS       100     /* Maksimum tespit edilecek yildiz */
#define MIN_STAR_PIXELS 3       /* Minimum piksel sayisi (gurultu filtresi) */
#define MAX_STAR_PIXELS 500     /* Maksimum piksel sayisi (buyuk nesneleri ele) */

/* --- Veri Yapilari --- */
typedef struct {
    float x;            /* Centroid X koordinati (sub-pixel) */
    float y;            /* Centroid Y koordinati (sub-pixel) */
    float brightness;   /* Toplam parlaklik */
    int   pixel_count;  /* Yildizi olusturan piksel sayisi */
    uint8_t peak;       /* En parlak piksel degeri */
} Star;

/* --- Global Degiskenler --- */
static uint8_t grayscale[IMG_HEIGHT][IMG_WIDTH];  /* Grayscale goruntu */
static uint8_t visited[IMG_HEIGHT][IMG_WIDTH];     /* Flood fill icin ziyaret haritasi */
static Star    detected_stars[MAX_STARS];           /* Tespit edilen yildizlar */
static int     num_stars = 0;                       /* Tespit edilen yildiz sayisi */

/* Flood fill icin piksel yigini */
#define STACK_SIZE 2048
static int stack_x[STACK_SIZE];
static int stack_y[STACK_SIZE];

/* --- Fonksiyon Prototipleri --- */
void read_framebuffer(void);
void apply_threshold_and_detect(void);
void flood_fill_centroid(int start_x, int start_y);
void send_results_uart(void);

/**
 * Framebuffer'dan pikselleri oku ve grayscale'e cevir
 */
void read_framebuffer(void)
{
    volatile uint32_t *fb = (volatile uint32_t *)WORK_FB_ADDR;
    int row, col;

    for (row = 0; row < IMG_HEIGHT; row++) {
        for (col = 0; col < IMG_WIDTH; col++) {
            uint32_t pixel = fb[row * IMG_WIDTH + col];

            /* 0x00RRGGBB formatindan RGB cikart */
            uint8_t r = (pixel >> 16) & 0xFF;
            uint8_t g = (pixel >> 8)  & 0xFF;
            uint8_t b = pixel & 0xFF;

            /* Grayscale: basit ortalama (hizli) */
            /* Alternatif: luminance = 0.299*R + 0.587*G + 0.114*B */
            grayscale[row][col] = (uint8_t)((r + g + b) / 3);
        }
    }
}

/**
 * Threshold uygula ve connected components ile yildizlari bul
 */
void apply_threshold_and_detect(void)
{
    int row, col;

    /* Ziyaret haritasini sifirla */
    memset(visited, 0, sizeof(visited));
    num_stars = 0;

    for (row = 0; row < IMG_HEIGHT; row++) {
        for (col = 0; col < IMG_WIDTH; col++) {
            /* Threshold ustu ve henuz ziyaret edilmemis piksel */
            if (grayscale[row][col] > THRESHOLD && !visited[row][col]) {
                if (num_stars < MAX_STARS) {
                    flood_fill_centroid(col, row);
                }
            }
        }
    }
}

/**
 * Flood fill ile bagli bileseni bul ve agirlikli centroid hesapla
 *
 * Agirlikli Centroid Formulu:
 *   x_c = SUM(x_i * I_i) / SUM(I_i)
 *   y_c = SUM(y_i * I_i) / SUM(I_i)
 *   burada I_i = piksel parlakligi (threshold cikarilmis)
 */
void flood_fill_centroid(int start_x, int start_y)
{
    float sum_x = 0.0f;    /* Agirlikli x toplami */
    float sum_y = 0.0f;    /* Agirlikli y toplami */
    float sum_w = 0.0f;    /* Toplam agirlik (parlaklik) */
    int   count = 0;        /* Piksel sayisi */
    uint8_t peak = 0;       /* En parlak piksel */

    /* Yigin tabanli flood fill (recursive degil - stack overflow onlemi) */
    int sp = 0;  /* Stack pointer */
    stack_x[sp] = start_x;
    stack_y[sp] = start_y;
    sp++;
    visited[start_y][start_x] = 1;

    while (sp > 0) {
        sp--;
        int cx = stack_x[sp];
        int cy = stack_y[sp];

        uint8_t val = grayscale[cy][cx];
        float weight = (float)(val - THRESHOLD);  /* Threshold cikarilmis agirlik */

        sum_x += (float)cx * weight;
        sum_y += (float)cy * weight;
        sum_w += weight;
        count++;

        if (val > peak) peak = val;

        /* 8-baglanti komsuluk (8-connectivity) */
        int dx, dy;
        for (dy = -1; dy <= 1; dy++) {
            for (dx = -1; dx <= 1; dx++) {
                if (dx == 0 && dy == 0) continue;

                int nx = cx + dx;
                int ny = cy + dy;

                /* Sinir kontrolu */
                if (nx < 0 || nx >= IMG_WIDTH || ny < 0 || ny >= IMG_HEIGHT)
                    continue;

                /* Ziyaret edilmemis ve threshold ustu */
                if (!visited[ny][nx] && grayscale[ny][nx] > THRESHOLD) {
                    visited[ny][nx] = 1;
                    if (sp < STACK_SIZE) {
                        stack_x[sp] = nx;
                        stack_y[sp] = ny;
                        sp++;
                    }
                }
            }
        }
    }

    /* Gurultu filtresi: cok kucuk veya cok buyuk bilesenleri ele */
    if (count < MIN_STAR_PIXELS || count > MAX_STAR_PIXELS)
        return;

    /* Centroid hesapla ve kaydet */
    if (sum_w > 0.0f && num_stars < MAX_STARS) {
        detected_stars[num_stars].x = sum_x / sum_w;
        detected_stars[num_stars].y = sum_y / sum_w;
        detected_stars[num_stars].brightness = sum_w;
        detected_stars[num_stars].pixel_count = count;
        detected_stars[num_stars].peak = peak;
        num_stars++;
    }
}

/**
 * Sonuclari UART uzerinden gonder
 * Format: CSV benzeri, Python tarafinda parse edilecek
 */
void send_results_uart(void)
{
    int i;

    printf("\r\n");
    printf("===== STAR TRACKER RESULTS =====\r\n");
    printf("Image: %dx%d, Threshold: %d\r\n", IMG_WIDTH, IMG_HEIGHT, THRESHOLD);
    printf("Stars detected: %d\r\n", num_stars);
    printf("--------------------------------\r\n");
    printf("ID,X,Y,BRIGHTNESS,PIXELS,PEAK\r\n");

    for (i = 0; i < num_stars; i++) {
        /* printf float MicroBlaze'de sorun cikarabilir, integer olarak gonder */
        int x_int = (int)(detected_stars[i].x * 100);  /* 2 ondalik, x100 */
        int y_int = (int)(detected_stars[i].y * 100);
        int brt   = (int)(detected_stars[i].brightness);

        printf("%d,%d.%02d,%d.%02d,%d,%d,%d\r\n",
               i,
               x_int / 100, x_int % 100,
               y_int / 100, y_int % 100,
               brt,
               detected_stars[i].pixel_count,
               detected_stars[i].peak);
    }

    printf("===== END RESULTS =====\r\n");
}

/**
 * Ana fonksiyon
 */
int main(void)
{
    printf("\r\n[Star Tracker] Baslatiliyor...\r\n");
    printf("[Star Tracker] Framebuffer adresi: 0x%08X\r\n", (unsigned int)WORK_FB_ADDR);
    printf("[Star Tracker] Goruntu boyutu: %dx%d\r\n", IMG_WIDTH, IMG_HEIGHT);

    /* Adim 1: Framebuffer'dan oku ve grayscale'e cevir */
    printf("[Star Tracker] Adim 1: Framebuffer okunuyor...\r\n");
    read_framebuffer();
    printf("[Star Tracker] Adim 1: Tamamlandi.\r\n");

    /* Adim 2: Threshold + Connected Component + Centroid */
    printf("[Star Tracker] Adim 2: Yildiz tespiti basliyor (threshold=%d)...\r\n", THRESHOLD);
    apply_threshold_and_detect();
    printf("[Star Tracker] Adim 2: Tamamlandi. %d yildiz tespit edildi.\r\n", num_stars);

    /* Adim 3: Sonuclari UART ile gonder */
    send_results_uart();

    printf("[Star Tracker] Bitti.\r\n");

    return 0;
}
