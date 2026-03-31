/************************************************************************/
/*  video_demo.c + Star Tracker Integration                             */
/*  Orijinal: Sam Bobrowicz, Digilent Inc. 2015                         */
/*  Star Tracker eklentisi: TUBITAK Uzay Projesi 2026                   */
/************************************************************************/

/* ------------------------------------------------------------ */
/*              Include File Definitions                        */
/* ------------------------------------------------------------ */

#include "video_demo.h"
#include "video_capture/video_capture.h"
#include "display_ctrl/display_ctrl.h"
#include "intc/intc.h"
#include <stdio.h>
#include "xuartlite_l.h"
#include "math.h"
#include <ctype.h>
#include <stdlib.h>
#include "xil_types.h"
#include "xil_cache.h"
#include "xparameters.h"
#include "sleep.h"

/*
 * XPAR redefines
 */
#define DYNCLK_BASEADDR XPAR_AXI_DYNCLK_0_S_AXI_LITE_BASEADDR
#define VGA_VDMA_ID XPAR_AXIVDMA_0_DEVICE_ID
#define DISP_VTC_ID XPAR_VTC_0_DEVICE_ID
#define VID_VTC_ID XPAR_VTC_1_DEVICE_ID
#define VID_GPIO_ID XPAR_AXI_GPIO_VIDEO_DEVICE_ID
#define VID_VTC_IRPT_ID XPAR_INTC_0_VTC_1_VEC_ID
#define VID_GPIO_IRPT_ID XPAR_INTC_0_GPIO_0_VEC_ID
#define SCU_TIMER_ID XPAR_AXI_TIMER_0_DEVICE_ID
#define UART_BASEADDR XPAR_UARTLITE_0_BASEADDR

/* ------------------------------------------------------------ */
/*           Star Tracker Parametreleri                         */
/* ------------------------------------------------------------ */

#define ST_MAX_WIDTH    1920
#define ST_MAX_HEIGHT   1080
#define ST_THRESHOLD    50
#define ST_MAX_STARS    100
#define ST_MIN_PIXELS   3
#define ST_MAX_PIXELS   500
#define ST_STACK_SIZE   8192
#define ST_FONT_SCALE   3

/* ------------------------------------------------------------ */
/*           Star Tracker Veri Yapilari                         */
/* ------------------------------------------------------------ */

typedef struct {
    int x_100;      /* Centroid X * 100 */
    int y_100;      /* Centroid Y * 100 */
    int brightness; /* Toplam parlaklik */
    int pixel_count;
    u8  peak;
} StarResult;

/* ------------------------------------------------------------ */
/*              Global Variables                                */
/* ------------------------------------------------------------ */

/*
 * Display and Video Driver structs
 */
DisplayCtrl dispCtrl;
XAxiVdma vdma;
VideoCapture videoCapt;
INTC intc;
char fRefresh;

/*
 * Framebuffers for video data
 */
u8 frameBuf[DISPLAY_NUM_FRAMES][DEMO_MAX_FRAME] __attribute__((aligned(128)));
u8 *pFrames[DISPLAY_NUM_FRAMES];

/*
 * Interrupt vector table
 */
const ivt_t ivt[] = {
	videoGpioIvt(VID_GPIO_IRPT_ID, &videoCapt),
	videoVtcIvt(VID_VTC_IRPT_ID, &(videoCapt.vtc))
};

/*
 * Star Tracker global verileri
 */
static u8          st_grayscale[ST_MAX_HEIGHT][ST_MAX_WIDTH];
static u8          st_visited[ST_MAX_HEIGHT][ST_MAX_WIDTH];
static StarResult  st_stars[ST_MAX_STARS];
static int         st_num_stars = 0;
static u16         st_stack_x[ST_STACK_SIZE];
static u16         st_stack_y[ST_STACK_SIZE];
static int         st_threshold = ST_THRESHOLD;

/* ------------------------------------------------------------ */
/*           Star Tracker Fonksiyonlari                        */
/* ------------------------------------------------------------ */

/*
 * Framebuffer'i grayscale'e cevir
 * Piksel formati: 24-bit (3 byte: R, B, G) - Digilent sirasi
 */
void StarTracker_ReadFrame(u8 *frame, u32 width, u32 height, u32 stride)
{
    u32 row, col;
    u32 lineStart = 0;

    for (row = 0; row < height && row < ST_MAX_HEIGHT; row++)
    {
        for (col = 0; col < width && col < ST_MAX_WIDTH; col++)
        {
            u32 idx = lineStart + col * 3;
            u8 r = frame[idx];
            u8 b = frame[idx + 1];
            u8 g = frame[idx + 2];
            st_grayscale[row][col] = (u8)(((u32)r + g + b) / 3);
        }
        lineStart += stride;
    }
}

/*
 * Flood fill + agirlikli centroid hesaplama
 */
void StarTracker_FloodFill(int start_x, int start_y, u32 width, u32 height)
{
    int sum_xw = 0, sum_yw = 0, sum_w = 0;
    int count = 0;
    u8  peak = 0;
    int sp = 0;

    st_stack_x[sp] = (u16)start_x;
    st_stack_y[sp] = (u16)start_y;
    sp++;
    st_visited[start_y][start_x] = 1;

    while (sp > 0)
    {
        sp--;
        int cx = st_stack_x[sp];
        int cy = st_stack_y[sp];
        u8  val = st_grayscale[cy][cx];
        int weight = (int)val - st_threshold;

        sum_xw += cx * weight;
        sum_yw += cy * weight;
        sum_w  += weight;
        count++;
        if (val > peak) peak = val;

        int dx, dy;
        for (dy = -1; dy <= 1; dy++)
        {
            for (dx = -1; dx <= 1; dx++)
            {
                if (dx == 0 && dy == 0) continue;
                int nx = cx + dx;
                int ny = cy + dy;
                if (nx < 0 || nx >= (int)width || ny < 0 || ny >= (int)height)
                    continue;
                if (!st_visited[ny][nx] && st_grayscale[ny][nx] > st_threshold)
                {
                    st_visited[ny][nx] = 1;
                    if (sp < ST_STACK_SIZE)
                    {
                        st_stack_x[sp] = (u16)nx;
                        st_stack_y[sp] = (u16)ny;
                        sp++;
                    }
                }
            }
        }
    }

    if (count < ST_MIN_PIXELS || count > ST_MAX_PIXELS)
        return;

    if (sum_w > 0 && st_num_stars < ST_MAX_STARS)
    {
        st_stars[st_num_stars].x_100 = (sum_xw * 100) / sum_w;
        st_stars[st_num_stars].y_100 = (sum_yw * 100) / sum_w;
        st_stars[st_num_stars].brightness = sum_w;
        st_stars[st_num_stars].pixel_count = count;
        st_stars[st_num_stars].peak = peak;
        st_num_stars++;
    }
}

/*
 * Yildiz tespiti: threshold + connected component + centroid
 */
void StarTracker_Detect(u32 width, u32 height)
{
    u32 row, col;
    /* Visited haritasini temizle */
    for (row = 0; row < height && row < ST_MAX_HEIGHT; row++)
        for (col = 0; col < width && col < ST_MAX_WIDTH; col++)
            st_visited[row][col] = 0;

    st_num_stars = 0;

    for (row = 0; row < height && row < ST_MAX_HEIGHT; row++)
    {
        for (col = 0; col < width && col < ST_MAX_WIDTH; col++)
        {
            if (st_grayscale[row][col] > st_threshold && !st_visited[row][col])
            {
                if (st_num_stars < ST_MAX_STARS)
                    StarTracker_FloodFill(col, row, width, height);
            }
        }
    }
}

/* ------------------------------------------------------------ */
/*           Overlay Cizim Fonksiyonlari (24-bit piksel)       */
/* ------------------------------------------------------------ */

/*
 * Tek piksel yaz - 24-bit format (R, B, G)
 */
void ST_DrawPixel(u8 *frame, int x, int y, u32 width, u32 stride,
                  u8 r, u8 g, u8 b)
{
    if (x < 0 || x >= (int)width || y < 0 || y >= ST_MAX_HEIGHT) return;
    u32 idx = (u32)y * stride + (u32)x * 3;
    frame[idx]     = r;
    frame[idx + 1] = b;  /* Digilent sirasi: R, B, G */
    frame[idx + 2] = g;
}

/*
 * Daire ciz (Midpoint circle)
 */
void ST_DrawCircle(u8 *frame, int cx, int cy, int rad, u32 width, u32 stride,
                   u8 r, u8 g, u8 b)
{
    int x = 0, y = rad, d = 1 - rad;
    while (x <= y)
    {
        ST_DrawPixel(frame, cx+x, cy+y, width, stride, r, g, b);
        ST_DrawPixel(frame, cx-x, cy+y, width, stride, r, g, b);
        ST_DrawPixel(frame, cx+x, cy-y, width, stride, r, g, b);
        ST_DrawPixel(frame, cx-x, cy-y, width, stride, r, g, b);
        ST_DrawPixel(frame, cx+y, cy+x, width, stride, r, g, b);
        ST_DrawPixel(frame, cx-y, cy+x, width, stride, r, g, b);
        ST_DrawPixel(frame, cx+y, cy-x, width, stride, r, g, b);
        ST_DrawPixel(frame, cx-y, cy-x, width, stride, r, g, b);
        if (d < 0) d += 2*x + 3;
        else { d += 2*(x-y) + 5; y--; }
        x++;
    }
}

/*
 * Arti isareti ciz
 */
void ST_DrawCrosshair(u8 *frame, int cx, int cy, int size, u32 width, u32 stride,
                      u8 r, u8 g, u8 b)
{
    int i;
    for (i = -size; i <= size; i++)
    {
        ST_DrawPixel(frame, cx+i, cy, width, stride, r, g, b);
        ST_DrawPixel(frame, cx, cy+i, width, stride, r, g, b);
    }
}

/*
 * Mini font (3x5, scale ile buyutulmus)
 */
static const u8 st_font[10][5] = {
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

void ST_DrawNumber(u8 *frame, int x, int y, int num, u32 width, u32 stride,
                   u8 r, u8 g, u8 b)
{
    int tens = num / 10;
    int ones = num % 10;
    int dx, dy, sx, sy;
    int s = ST_FONT_SCALE;

    if (num >= 10)
    {
        for (dy = 0; dy < 5; dy++)
            for (dx = 0; dx < 3; dx++)
                if (st_font[tens][dy] & (0x4 >> dx))
                    for (sy = 0; sy < s; sy++)
                        for (sx = 0; sx < s; sx++)
                            ST_DrawPixel(frame, x+dx*s+sx, y+dy*s+sy,
                                         width, stride, r, g, b);
        x += 4 * s;
    }
    for (dy = 0; dy < 5; dy++)
        for (dx = 0; dx < 3; dx++)
            if (st_font[ones][dy] & (0x4 >> dx))
                for (sy = 0; sy < s; sy++)
                    for (sx = 0; sx < s; sx++)
                        ST_DrawPixel(frame, x+dx*s+sx, y+dy*s+sy,
                                     width, stride, r, g, b);
}

/*
 * Tum tespit edilen yildizlarin overlay'ini ciz
 */
void StarTracker_DrawOverlays(u8 *frame, u32 width, u32 stride)
{
    int i;
    for (i = 0; i < st_num_stars; i++)
    {
        int cx = st_stars[i].x_100 / 100;
        int cy = st_stars[i].y_100 / 100;

        /* Yesil daire (3px kalin) */
        ST_DrawCircle(frame, cx, cy, 16, width, stride, 0, 255, 0);
        ST_DrawCircle(frame, cx, cy, 17, width, stride, 0, 255, 0);
        ST_DrawCircle(frame, cx, cy, 18, width, stride, 0, 255, 0);

        /* Kirmizi arti */
        ST_DrawCrosshair(frame, cx, cy,   6, width, stride, 255, 0, 0);
        ST_DrawCrosshair(frame, cx, cy+1, 6, width, stride, 255, 0, 0);

        /* Sari ID numarasi */
        ST_DrawNumber(frame, cx+22, cy-12, i, width, stride, 255, 255, 0);
    }
}

/*
 * Star Tracker sonuclarini UART'tan gonder
 */
void StarTracker_PrintResults(void)
{
    int i;
    xil_printf("\r\n===== STAR TRACKER RESULTS =====\r\n");
    xil_printf("Resolution: %dx%d, Threshold: %d\r\n",
               dispCtrl.vMode.width, dispCtrl.vMode.height, st_threshold);
    xil_printf("Stars detected: %d\r\n", st_num_stars);
    xil_printf("--------------------------------\r\n");
    xil_printf("ID,X,Y,BRIGHTNESS,PIXELS,PEAK\r\n");

    for (i = 0; i < st_num_stars; i++)
    {
        int x_w = st_stars[i].x_100 / 100;
        int x_f = st_stars[i].x_100 % 100;
        int y_w = st_stars[i].y_100 / 100;
        int y_f = st_stars[i].y_100 % 100;
        if (x_f < 0) x_f = -x_f;
        if (y_f < 0) y_f = -y_f;
        xil_printf("%d,%d.%02d,%d.%02d,%d,%d,%d\r\n",
                   i, x_w, x_f, y_w, y_f,
                   st_stars[i].brightness,
                   st_stars[i].pixel_count,
                   (int)st_stars[i].peak);
    }
    xil_printf("===== END RESULTS =====\r\n");
}

/*
 * Star Tracker tam calisma dongusu:
 *   1. Mevcut framebuffer'i oku -> grayscale
 *   2. Yildiz tespiti yap
 *   3. Overlay ciz (ayni framebuffer'a)
 *   4. Cache flush
 *   5. Sonuclari UART'tan gonder
 */
void StarTracker_Run(void)
{
    u8 *frame = pFrames[dispCtrl.curFrame];
    u32 width = dispCtrl.vMode.width;
    u32 height = dispCtrl.vMode.height;
    u32 stride = DEMO_STRIDE;

    xil_printf("\r\n[Star Tracker] Baslatiliyor...\r\n");
    xil_printf("[Star Tracker] Cozunurluk: %dx%d, Threshold: %d\r\n",
               width, height, st_threshold);

    /* Adim 1: Grayscale donusum */
    xil_printf("[Star Tracker] Adim 1: Framebuffer okunuyor...\r\n");
    StarTracker_ReadFrame(frame, width, height, stride);
    xil_printf("[Star Tracker] Adim 1: OK\r\n");

    /* Adim 2: Yildiz tespiti */
    xil_printf("[Star Tracker] Adim 2: Yildiz tespiti...\r\n");
    StarTracker_Detect(width, height);
    xil_printf("[Star Tracker] Adim 2: OK - %d yildiz bulundu.\r\n", st_num_stars);

    /* Adim 3: Overlay ciz */
    xil_printf("[Star Tracker] Adim 3: Overlay ciziliyor...\r\n");
    StarTracker_DrawOverlays(frame, width, stride);
    Xil_DCacheFlushRange((unsigned int)frame, DEMO_MAX_FRAME);
    xil_printf("[Star Tracker] Adim 3: OK - Monitorde gormelisiniz!\r\n");

    /* Adim 4: UART sonuc raporu */
    StarTracker_PrintResults();

    xil_printf("[Star Tracker] Bitti.\r\n");
}

/*
 * Basit pseudo-random sayi ureteci (LCG)
 */
static u32 st_rand_state = 12345;

u32 st_rand(void)
{
    st_rand_state = st_rand_state * 1103515245 + 12345;
    return (st_rand_state >> 16) & 0x7FFF;
}

/*
 * Sentetik yildiz alani olustur ve framebuffer'a yaz
 * Gaussian PSF'yi basit bir 2D dagilim ile taklit eder
 */
void StarTracker_GenerateStarfield(void)
{
    u8 *frame = pFrames[dispCtrl.curFrame];
    u32 width = dispCtrl.vMode.width;
    u32 height = dispCtrl.vMode.height;
    u32 stride = DEMO_STRIDE;
    int num_gen_stars = 35;
    int i, dx, dy;

    xil_printf("\r\n[Star Tracker] Sentetik yildiz alani olusturuluyor...\r\n");
    xil_printf("[Star Tracker] Cozunurluk: %dx%d, %d yildiz\r\n",
               width, height, num_gen_stars);

    /* Adim 1: Tum framebuffer'i siyah yap (hafif gurultu ile) */
    u32 row, col;
    u32 lineStart = 0;
    for (row = 0; row < height; row++)
    {
        for (col = 0; col < width; col++)
        {
            u32 idx = lineStart + col * 3;
            u8 noise = (u8)(st_rand() % 20);  /* 0-19 arasi gurultu */
            frame[idx]     = noise;  /* R */
            frame[idx + 1] = noise;  /* B */
            frame[idx + 2] = noise;  /* G */
        }
        lineStart += stride;
    }

    /* Adim 2: Rastgele yildizlar ekle (Gaussian PSF benzeri) */
    st_rand_state = 42;  /* Tekrarlanabilir sonuc */

    for (i = 0; i < num_gen_stars; i++)
    {
        int cx = 40 + (st_rand() % (width - 80));
        int cy = 40 + (st_rand() % (height - 80));
        int brightness = 100 + (st_rand() % 156);  /* 100-255 */
        int sigma_x10 = 15 + (st_rand() % 20);     /* 1.5 - 3.5 piksel (*10) */

        /* Gaussian PSF: radius = 3*sigma kadar ciz */
        int radius = (sigma_x10 * 3) / 10 + 1;

        for (dy = -radius; dy <= radius; dy++)
        {
            for (dx = -radius; dx <= radius; dx++)
            {
                int px = cx + dx;
                int py = cy + dy;
                if (px < 0 || px >= (int)width || py < 0 || py >= (int)height)
                    continue;

                /* dist_sq = dx*dx + dy*dy, sigma_sq = (sigma/10)^2 */
                /* PSF = brightness * exp(-dist_sq / (2*sigma_sq)) */
                /* Tam exp yerine basit yaklasim: triangle + quadratic falloff */
                int dist_sq_x100 = (dx*dx + dy*dy) * 100;
                int sigma_sq_x100 = (sigma_x10 * sigma_x10);  /* zaten *100 */
                int ratio = dist_sq_x100 / (sigma_sq_x100 / 50 + 1); /* 2*sigma^2 icin /50 */

                int val;
                if (ratio < 50)
                    val = brightness;
                else if (ratio < 200)
                    val = brightness * (200 - ratio) / 200;
                else
                    val = 0;

                if (val > 0)
                {
                    u32 idx = (u32)py * stride + (u32)px * 3;
                    int cur = frame[idx];
                    int nv = cur + val;
                    if (nv > 255) nv = 255;
                    frame[idx]     = (u8)nv;
                    frame[idx + 1] = (u8)nv;
                    frame[idx + 2] = (u8)nv;
                }
            }
        }
    }

    Xil_DCacheFlushRange((unsigned int)frame, DEMO_MAX_FRAME);
    xil_printf("[Star Tracker] Yildiz alani olusturuldu! Monitorde gorunmeli.\r\n");
    xil_printf("[Star Tracker] Simdi '9' ile Star Tracker calistirabilirsiniz.\r\n");
}

/*
 * Overlay'i temizle: mevcut frame'i siyahla doldur veya
 * test pattern ile degistir
 */
void StarTracker_ClearOverlay(void)
{
    xil_printf("\r\n[Star Tracker] Overlay temizleniyor...\r\n");
    DemoPrintTest(pFrames[dispCtrl.curFrame],
                  dispCtrl.vMode.width, dispCtrl.vMode.height,
                  DEMO_STRIDE, DEMO_PATTERN_1);
    xil_printf("[Star Tracker] Overlay temizlendi (color bar pattern).\r\n");
}

/*
 * Threshold degistir
 */
void StarTracker_ChangeThreshold(void)
{
    char c;
    xil_printf("\r\nMevcut threshold: %d\r\n", st_threshold);
    xil_printf("  + : Artir (+10)\r\n");
    xil_printf("  - : Azalt (-10)\r\n");
    xil_printf("  q : Geri don\r\n");

    while (1)
    {
        while (XUartLite_IsReceiveEmpty(UART_BASEADDR)) {}
        c = XUartLite_ReadReg(UART_BASEADDR, XUL_RX_FIFO_OFFSET);

        if (c == '+' || c == '=')
        {
            st_threshold += 10;
            if (st_threshold > 200) st_threshold = 200;
        }
        else if (c == '-')
        {
            st_threshold -= 10;
            if (st_threshold < 10) st_threshold = 10;
        }
        else if (c == 'q')
        {
            break;
        }
        xil_printf("  Threshold: %d\r\n", st_threshold);
    }
}

/* ------------------------------------------------------------ */
/*       Orijinal Demo Fonksiyonlari (degistirilmemis)         */
/* ------------------------------------------------------------ */

int main(void)
{
	Xil_ICacheEnable();
	Xil_DCacheEnable();

	DemoInitialize();

	DemoRun();

	return 0;
}

void DemoInitialize()
{
	int Status;
	XAxiVdma_Config *vdmaConfig;
	int i;

	for (i = 0; i < DISPLAY_NUM_FRAMES; i++)
	{
		pFrames[i] = frameBuf[i];
	}

	vdmaConfig = XAxiVdma_LookupConfig(VGA_VDMA_ID);
	if (!vdmaConfig)
	{
		xil_printf("No video DMA found for ID %d\r\n", VGA_VDMA_ID);
		return;
	}
	Status = XAxiVdma_CfgInitialize(&vdma, vdmaConfig, vdmaConfig->BaseAddress);
	if (Status != XST_SUCCESS)
	{
		xil_printf("VDMA Configuration Initialization failed %d\r\n", Status);
		return;
	}

	Status = DisplayInitialize(&dispCtrl, &vdma, DISP_VTC_ID, DYNCLK_BASEADDR, pFrames, DEMO_STRIDE);
	if (Status != XST_SUCCESS)
	{
		xil_printf("Display Ctrl initialization failed during demo initialization%d\r\n", Status);
		return;
	}
	Status = DisplayStart(&dispCtrl);
	if (Status != XST_SUCCESS)
	{
		xil_printf("Couldn't start display during demo initialization%d\r\n", Status);
		return;
	}

	Status = fnInitInterruptController(&intc);
	if(Status != XST_SUCCESS) {
		xil_printf("Error initializing interrupts");
		return;
	}
	fnEnableInterrupts(&intc, &ivt[0], sizeof(ivt)/sizeof(ivt[0]));

	Status = VideoInitialize(&videoCapt, &intc, &vdma, VID_GPIO_ID, VID_VTC_ID, VID_VTC_IRPT_ID, pFrames, DEMO_STRIDE, DEMO_START_ON_DET);
	if (Status != XST_SUCCESS)
	{
		xil_printf("Video Ctrl initialization failed during demo initialization%d\r\n", Status);
		return;
	}

	VideoSetCallback(&videoCapt, DemoISR, &fRefresh);

	DemoPrintTest(dispCtrl.framePtr[dispCtrl.curFrame], dispCtrl.vMode.width, dispCtrl.vMode.height, dispCtrl.stride, DEMO_PATTERN_1);

	return;
}

/*
 * DemoRun - Genisletilmis menu (Star Tracker eklenmis)
 */
void DemoRun()
{
	int nextFrame = 0;
	char userInput = 0;
	u32 locked;
	XGpio *GpioPtr = &videoCapt.gpio;

	/* Flush UART FIFO */
	while (!XUartLite_IsReceiveEmpty(UART_BASEADDR))
	{
		XUartLite_ReadReg(UART_BASEADDR, XUL_RX_FIFO_OFFSET);
	}
	while (userInput != 'q')
	{
		fRefresh = 0;
		DemoPrintMenu();

		/* Wait for data on UART */
		while (XUartLite_IsReceiveEmpty(UART_BASEADDR) && !fRefresh)
		{}

		if (!XUartLite_IsReceiveEmpty(UART_BASEADDR))
		{
			userInput = XUartLite_ReadReg(UART_BASEADDR, XUL_RX_FIFO_OFFSET);
			xil_printf("%c", userInput);
		}
		else
		{
			userInput = 'r';
		}

		switch (userInput)
		{
		case '1':
			DemoChangeRes();
			break;
		case '2':
			nextFrame = dispCtrl.curFrame + 1;
			if (nextFrame >= DISPLAY_NUM_FRAMES)
			{
				nextFrame = 0;
			}
			DisplayChangeFrame(&dispCtrl, nextFrame);
			break;
		case '3':
			DemoPrintTest(pFrames[dispCtrl.curFrame], dispCtrl.vMode.width, dispCtrl.vMode.height, DEMO_STRIDE, DEMO_PATTERN_0);
			break;
		case '4':
			DemoPrintTest(pFrames[dispCtrl.curFrame], dispCtrl.vMode.width, dispCtrl.vMode.height, DEMO_STRIDE, DEMO_PATTERN_1);
			break;
		case '5':
			if (videoCapt.state == VIDEO_STREAMING)
				VideoStop(&videoCapt);
			else
				VideoStart(&videoCapt);
			break;
		case '6':
			nextFrame = videoCapt.curFrame + 1;
			if (nextFrame >= DISPLAY_NUM_FRAMES)
			{
				nextFrame = 0;
			}
			VideoChangeFrame(&videoCapt, nextFrame);
			break;
		case '7':
			nextFrame = videoCapt.curFrame + 1;
			if (nextFrame >= DISPLAY_NUM_FRAMES)
			{
				nextFrame = 0;
			}
			VideoStop(&videoCapt);
			DemoInvertFrame(pFrames[videoCapt.curFrame], pFrames[nextFrame], videoCapt.timing.HActiveVideo, videoCapt.timing.VActiveVideo, DEMO_STRIDE);
			VideoStart(&videoCapt);
			DisplayChangeFrame(&dispCtrl, nextFrame);
			break;
		case '8':
			nextFrame = videoCapt.curFrame + 1;
			if (nextFrame >= DISPLAY_NUM_FRAMES)
			{
				nextFrame = 0;
			}
			VideoStop(&videoCapt);
			DemoScaleFrame(pFrames[videoCapt.curFrame], pFrames[nextFrame], videoCapt.timing.HActiveVideo, videoCapt.timing.VActiveVideo, dispCtrl.vMode.width, dispCtrl.vMode.height, DEMO_STRIDE);
			VideoStart(&videoCapt);
			DisplayChangeFrame(&dispCtrl, nextFrame);
			break;

		/* ========== STAR TRACKER KOMUTLARI ========== */
		case '9':
			StarTracker_Run();
			break;
		case '0':
			StarTracker_ClearOverlay();
			break;
		case 'g':
			StarTracker_GenerateStarfield();
			break;
		case 't':
			StarTracker_ChangeThreshold();
			break;
		/* ============================================ */

		case 'q':
			break;
		case 'r':
			locked = XGpio_DiscreteRead(GpioPtr, 2);
			xil_printf("%d", locked);
			break;
		default :
			xil_printf("\n\rInvalid Selection");
			usleep(50000);
		}
	}

	return;
}

/*
 * DemoPrintMenu - Genisletilmis (Star Tracker eklenmis)
 */
void DemoPrintMenu()
{
	xil_printf("\x1B[H");
	xil_printf("\x1B[2J");
	xil_printf("**************************************************\n\r");
	xil_printf("*    Nexys Video HDMI Demo + Star Tracker        *\n\r");
	xil_printf("**************************************************\n\r");
	xil_printf("*Display Resolution: %28s*\n\r", dispCtrl.vMode.label);
	printf("*Display Pixel Clock Freq. (MHz): %15.3f*\n\r", dispCtrl.pxlFreq);
	xil_printf("*Display Frame Index: %27d*\n\r", dispCtrl.curFrame);
	if (videoCapt.state == VIDEO_DISCONNECTED) xil_printf("*Video Capture Resolution: %22s*\n\r", "!HDMI UNPLUGGED!");
	else xil_printf("*Video Capture Resolution: %17dx%-4d*\n\r", videoCapt.timing.HActiveVideo, videoCapt.timing.VActiveVideo);
	xil_printf("*Video Frame Index: %29d*\n\r", videoCapt.curFrame);
	xil_printf("*Star Tracker Threshold: %24d*\n\r", st_threshold);
	xil_printf("*Stars Detected: %31d*\n\r", st_num_stars);
	xil_printf("**************************************************\n\r");
	xil_printf("\n\r");
	xil_printf("--- Display / Video ---\n\r");
	xil_printf("1 - Change Display Resolution\n\r");
	xil_printf("2 - Change Display Framebuffer Index\n\r");
	xil_printf("3 - Print Blended Test Pattern\n\r");
	xil_printf("4 - Print Color Bar Test Pattern\n\r");
	xil_printf("5 - Start/Stop Video stream\n\r");
	xil_printf("6 - Change Video Framebuffer Index\n\r");
	xil_printf("7 - Grab Video Frame and invert colors\n\r");
	xil_printf("8 - Grab Video Frame and scale\n\r");
	xil_printf("\n\r");
	xil_printf("--- Star Tracker ---\n\r");
	xil_printf("g - Generate Starfield (sentetik yildiz alani olustur)\n\r");
	xil_printf("9 - Run Star Tracker (detect + overlay)\n\r");
	xil_printf("0 - Clear Overlay (reset to color bars)\n\r");
	xil_printf("t - Change Threshold (current: %d)\n\r", st_threshold);
	xil_printf("\n\r");
	xil_printf("q - Quit\n\r");
	xil_printf("\n\r");
	xil_printf("Enter a selection:");
}

/* Orijinal fonksiyonlar - degistirilmedi */

void DemoChangeRes()
{
	int fResSet = 0;
	int status;
	char userInput = 0;

	while (!XUartLite_IsReceiveEmpty(UART_BASEADDR))
		{
			XUartLite_ReadReg(UART_BASEADDR, XUL_RX_FIFO_OFFSET);
		}

	while (!fResSet)
	{
		DemoCRMenu();

		while (XUartLite_IsReceiveEmpty(UART_BASEADDR) && !fRefresh)
		{}

		userInput = XUartLite_ReadReg(UART_BASEADDR, XUL_RX_FIFO_OFFSET);
		xil_printf("%c", userInput);
		status = XST_SUCCESS;
		switch (userInput)
		{
		case '1':
			status = DisplayStop(&dispCtrl);
			DisplaySetMode(&dispCtrl, &VMODE_640x480);
			DisplayStart(&dispCtrl);
			fResSet = 1;
			break;
		case '2':
			status = DisplayStop(&dispCtrl);
			DisplaySetMode(&dispCtrl, &VMODE_800x600);
			DisplayStart(&dispCtrl);
			fResSet = 1;
			break;
		case '3':
			status = DisplayStop(&dispCtrl);
			DisplaySetMode(&dispCtrl, &VMODE_1280x720);
			DisplayStart(&dispCtrl);
			fResSet = 1;
			break;
		case '4':
			status = DisplayStop(&dispCtrl);
			DisplaySetMode(&dispCtrl, &VMODE_1280x1024);
			DisplayStart(&dispCtrl);
			fResSet = 1;
			break;
		case '5':
			status = DisplayStop(&dispCtrl);
			DisplaySetMode(&dispCtrl, &VMODE_1920x1080);
			DisplayStart(&dispCtrl);
			fResSet = 1;
			break;
		case 'q':
			fResSet = 1;
			break;
		default :
			xil_printf("\n\rInvalid Selection");
			usleep(50000);
		}
		if (status == XST_DMA_ERROR)
		{
			xil_printf("\n\rWARNING: AXI VDMA Error detected and cleared\n\r");
		}
	}
}

void DemoCRMenu()
{
	xil_printf("\x1B[H");
	xil_printf("\x1B[2J");
	xil_printf("**************************************************\n\r");
	xil_printf("*    Nexys Video HDMI Demo + Star Tracker        *\n\r");
	xil_printf("**************************************************\n\r");
	xil_printf("*Current Resolution: %28s*\n\r", dispCtrl.vMode.label);
	printf("*Pixel Clock Freq. (MHz): %23.3f*\n\r", dispCtrl.pxlFreq);
	xil_printf("**************************************************\n\r");
	xil_printf("\n\r");
	xil_printf("1 - %s\n\r", VMODE_640x480.label);
	xil_printf("2 - %s\n\r", VMODE_800x600.label);
	xil_printf("3 - %s\n\r", VMODE_1280x720.label);
	xil_printf("4 - %s\n\r", VMODE_1280x1024.label);
	xil_printf("5 - %s\n\r", VMODE_1920x1080.label);
	xil_printf("q - Quit (don't change resolution)\n\r");
	xil_printf("\n\r");
	xil_printf("Select a new resolution:");
}

void DemoInvertFrame(u8 *srcFrame, u8 *destFrame, u32 width, u32 height, u32 stride)
{
	u32 xcoi, ycoi;
	u32 lineStart = 0;
	for(ycoi = 0; ycoi < height; ycoi++)
	{
		for(xcoi = 0; xcoi < (width * 3); xcoi+=3)
		{
			destFrame[xcoi + lineStart] = ~srcFrame[xcoi + lineStart];
			destFrame[xcoi + lineStart + 1] = ~srcFrame[xcoi + lineStart + 1];
			destFrame[xcoi + lineStart + 2] = ~srcFrame[xcoi + lineStart + 2];
		}
		lineStart += stride;
	}
	Xil_DCacheFlushRange((unsigned int) destFrame, DEMO_MAX_FRAME);
}

void DemoScaleFrame(u8 *srcFrame, u8 *destFrame, u32 srcWidth, u32 srcHeight, u32 destWidth, u32 destHeight, u32 stride)
{
	float xInc, yInc;
	float xcoSrc, ycoSrc;
	float x1y1, x2y1, x1y2, x2y2;
	int ix1y1, ix2y1, ix1y2, ix2y2;
	float xDist, yDist;
	int xcoDest, ycoDest;
	int iy1;
	int iDest;
	int i;

	xInc = ((float) srcWidth - 1.0) / ((float) destWidth);
	yInc = ((float) srcHeight - 1.0) / ((float) destHeight);

	ycoSrc = 0.0;
	for (ycoDest = 0; ycoDest < destHeight; ycoDest++)
	{
		iy1 = ((int) ycoSrc) * stride;
		yDist = ycoSrc - ((float) ((int) ycoSrc));
		iDest = ycoDest * stride;
		xcoSrc = 0.0;
		for (xcoDest = 0; xcoDest < destWidth; xcoDest++)
		{
			ix1y1 = iy1 + ((int) xcoSrc) * 3;
			ix2y1 = ix1y1 + 3;
			ix1y2 = ix1y1 + stride;
			ix2y2 = ix1y1 + stride + 3;
			xDist = xcoSrc - ((float) ((int) xcoSrc));
			for (i = 0; i < 3; i++)
			{
				x1y1 = (float) srcFrame[ix1y1 + i];
				x2y1 = (float) srcFrame[ix2y1 + i];
				x1y2 = (float) srcFrame[ix1y2 + i];
				x2y2 = (float) srcFrame[ix2y2 + i];
				destFrame[iDest] = (u8) ((1.0-yDist)*((1.0-xDist)*x1y1+xDist*x2y1) + yDist*((1.0-xDist)*x1y2+xDist*x2y2));
				iDest++;
			}
			xcoSrc += xInc;
		}
		ycoSrc += yInc;
	}
	Xil_DCacheFlushRange((unsigned int) destFrame, DEMO_MAX_FRAME);
	return;
}

void DemoPrintTest(u8 *frame, u32 width, u32 height, u32 stride, int pattern)
{
	u32 xcoi, ycoi;
	u32 iPixelAddr;
	u8 wRed, wBlue, wGreen;
	u32 wCurrentInt;
	double fRed, fBlue, fGreen, fColor;
	u32 xLeft, xMid, xRight, xInt;
	u32 yMid, yInt;
	double xInc, yInc;

	switch (pattern)
	{
	case DEMO_PATTERN_0:
		xInt = width / 4;
		xLeft = xInt * 3;
		xMid = xInt * 2 * 3;
		xRight = xInt * 3 * 3;
		xInc = 256.0 / ((double) xInt);
		yInt = height / 2;
		yMid = yInt;
		yInc = 256.0 / ((double) yInt);
		fBlue = 0.0;
		fRed = 256.0;
		for(xcoi = 0; xcoi < (width*3); xcoi+=3)
		{
			wRed = (fRed >= 256.0) ? 255 : ((u8) fRed);
			wBlue = (fBlue >= 256.0) ? 255 : ((u8) fBlue);
			iPixelAddr = xcoi;
			fGreen = 0.0;
			for(ycoi = 0; ycoi < height; ycoi++)
			{
				wGreen = (fGreen >= 256.0) ? 255 : ((u8) fGreen);
				frame[iPixelAddr] = wRed;
				frame[iPixelAddr + 1] = wBlue;
				frame[iPixelAddr + 2] = wGreen;
				if (ycoi < yMid) fGreen += yInc;
				else fGreen -= yInc;
				iPixelAddr += stride;
			}
			if (xcoi < xLeft) { fBlue = 0.0; fRed -= xInc; }
			else if (xcoi < xMid) { fBlue += xInc; fRed += xInc; }
			else if (xcoi < xRight) { fBlue -= xInc; fRed -= xInc; }
			else { fBlue += xInc; fRed = 0; }
		}
		Xil_DCacheFlushRange((unsigned int) frame, DEMO_MAX_FRAME);
		break;
	case DEMO_PATTERN_1:
		xInt = width / 7;
		xInc = 256.0 / ((double) xInt);
		fColor = 0.0;
		wCurrentInt = 1;
		for(xcoi = 0; xcoi < (width*3); xcoi+=3)
		{
			if (wCurrentInt > 7) { wRed = 255; wBlue = 255; wGreen = 255; }
			else
			{
				if (wCurrentInt & 0b001) wRed = (u8) fColor; else wRed = 0;
				if (wCurrentInt & 0b010) wBlue = (u8) fColor; else wBlue = 0;
				if (wCurrentInt & 0b100) wGreen = (u8) fColor; else wGreen = 0;
			}
			iPixelAddr = xcoi;
			for(ycoi = 0; ycoi < height; ycoi++)
			{
				frame[iPixelAddr] = wRed;
				frame[iPixelAddr + 1] = wBlue;
				frame[iPixelAddr + 2] = wGreen;
				iPixelAddr += stride;
			}
			fColor += xInc;
			if (fColor >= 256.0) { fColor = 0.0; wCurrentInt++; }
		}
		Xil_DCacheFlushRange((unsigned int) frame, DEMO_MAX_FRAME);
		break;
	default :
		xil_printf("Error: invalid pattern passed to DemoPrintTest");
	}
}

void DemoISR(void *callBackRef, void *pVideo)
{
	char *data = (char *) callBackRef;
	*data = 1;
}
