#include "st7789.hpp"

#include <cstdlib>
#include <math.h>

extern uint32_t framebuffer[];
namespace pimoroni {
  
  //uint32_t framebuffer[160 * 120];
  uint16_t backbuffer[160 * 240];
  //uint16_t linebuffer[160 * 2];

  enum MADCTL : uint8_t {
    ROW_ORDER   = 0b10000000,
    COL_ORDER   = 0b01000000,
    SWAP_XY     = 0b00100000,  // AKA "MV"
    SCAN_ORDER  = 0b00010000,
    RGB_BGR     = 0b00001000,
    HORIZ_ORDER = 0b00000100
  };

  enum reg {
    SWRESET   = 0x01,
    TEOFF     = 0x34,
    TEON      = 0x35,
    MADCTL    = 0x36,
    COLMOD    = 0x3A,
    RAMCTRL   = 0xB0,
    GCTRL     = 0xB7,
    VCOMS     = 0xBB,
    LCMCTRL   = 0xC0,
    VDVVRHEN  = 0xC2,
    VRHS      = 0xC3,
    VDVS      = 0xC4,
    FRCTRL2   = 0xC6,
    PWCTRL1   = 0xD0,
    PORCTRL   = 0xB2,
    GMCTRP1   = 0xE0,
    GMCTRN1   = 0xE1,
    INVOFF    = 0x20,
    SLPIN     = 0x10,
    SLPOUT    = 0x11,
    DISPON    = 0x29,
    GAMSET    = 0x26,
    DISPOFF   = 0x28,
    RAMWR     = 0x2C,
    INVON     = 0x21,
    CASET     = 0x2A,
    RASET     = 0x2B,
    PWMFRSEL  = 0xCC
  };

  void ST7789::init() {
    gpio_set_function(dc, GPIO_FUNC_SIO);
    gpio_set_dir(dc, GPIO_OUT);

    gpio_set_function(cs, GPIO_FUNC_SIO);
    gpio_set_dir(cs, GPIO_OUT);

    // if a backlight pin is provided then set it up for
    // pwm control
    pwm_config cfg = pwm_get_default_config();
    pwm_set_wrap(pwm_gpio_to_slice_num(bl), 65535);
    pwm_init(pwm_gpio_to_slice_num(bl), &cfg, true);
    gpio_set_function(bl, GPIO_FUNC_PWM);
    set_backlight(0); // Turn backlight off initially to avoid nasty surprises

    command(reg::SWRESET);

    sleep_ms(150);

    // Common init
    command(reg::TEON);  // enable frame sync signal if used
    command(reg::COLMOD,    1, "\x05");  // 16 bits per pixel

    command(reg::PORCTRL, 5, "\x0c\x0c\x00\x33\x33");
    command(reg::LCMCTRL, 1, "\x2c");
    command(reg::VDVVRHEN, 1, "\x01");
    command(reg::VRHS, 1, "\x12");
    command(reg::VDVS, 1, "\x20");
    command(reg::PWCTRL1, 2, "\xa4\xa1");
    command(reg::FRCTRL2, 1, "\x0f");

    // As noted in https://github.com/pimoroni/pimoroni-pico/issues/1040
    // this is required to avoid a weird light grey banding issue with low brightness green.
    // The banding is not visible without tweaking gamma settings (GMCTRP1 & GMCTRN1) but
    // it makes sense to fix it anyway.
    command(reg::RAMCTRL, 2, "\x00\xc0");

    // 320 x 240
    command(reg::GCTRL, 1, "\x35");
    command(reg::VCOMS, 1, "\x1f");
    command(reg::GMCTRP1, 14, "\xD0\x08\x11\x08\x0C\x15\x39\x33\x50\x36\x13\x14\x29\x2D");
    command(reg::GMCTRN1, 14, "\xD0\x08\x10\x08\x06\x06\x39\x44\x51\x0B\x16\x14\x2F\x31");

    command(reg::INVON);   // set inversion mode
    command(reg::SLPOUT);  // leave sleep mode
    command(reg::DISPON);  // turn display on

    sleep_ms(100);

    uint8_t madctl = MADCTL::ROW_ORDER | MADCTL::SWAP_XY | MADCTL::SCAN_ORDER;
    uint16_t caset[2] = {0, 319};
    uint16_t raset[2] = {0, 239};
  
    // Byte swap the 16bit rows/cols values
    caset[0] = __builtin_bswap16(caset[0]);
    caset[1] = __builtin_bswap16(caset[1]);
    raset[0] = __builtin_bswap16(raset[0]);
    raset[1] = __builtin_bswap16(raset[1]);

    command(reg::CASET,  4, (char *)caset);
    command(reg::RASET,  4, (char *)raset);
    command(reg::MADCTL, 1, (char *)&madctl);

    update();
    set_backlight(255); // Turn backlight on now surprises have passed
  }

  uint32_t *ST7789::get_framebuffer() {
    return framebuffer;
  }

  void ST7789::write_blocking_dma(const uint8_t *src, size_t len) {
    while (dma_channel_is_busy(st_dma))
      ;
    dma_channel_set_trans_count(st_dma, len, false);
    dma_channel_set_read_addr(st_dma, src, true);
  }

  void ST7789::write_blocking_parallel(const uint8_t *src, size_t len) {
    write_blocking_dma(src, len);
    dma_channel_wait_for_finish_blocking(st_dma);

    // This may cause a race between PIO and the
    // subsequent chipselect deassert for the last pixel
    while(!pio_sm_is_tx_fifo_empty(parallel_pio, parallel_sm))
      ;
  }

  void ST7789::command(uint8_t command, size_t len, const char *data) {
    gpio_put(dc, 0); // command mode

    gpio_put(cs, 0);

    write_blocking_parallel(&command, 1);

    if(data) {
      gpio_put(dc, 1); // data mode
      write_blocking_parallel((const uint8_t*)data, len);
    }

    gpio_put(cs, 1);
  }

  void ST7789::update() {
    uint8_t cmd = reg::RAMWR;

    if(!display_on) {
      command(reg::DISPON);  // turn display on
      sleep_ms(100);
      display_on = true;
    }

    // Determine clock divider
    constexpr uint32_t max_pio_clk = 50 * MHZ;
    const uint32_t sys_clk_hz = clock_get_hz(clk_sys);

    // Relying on the fact that (n + n - 1) / n gives us ~1.98 and rounds (truncates) down to 1
    const uint32_t clk_div = (sys_clk_hz + max_pio_clk - 1) / max_pio_clk;

    pio_sm_set_clkdiv(parallel_pio, parallel_pd_sm, clk_div);
  
    dma_channel_wait_for_finish_blocking(pd_st_dma);
    while(!pio_sm_is_tx_fifo_empty(parallel_pio, parallel_pd_sm))
      ;

    uint8_t *src = (uint8_t *)framebuffer;
    uint16_t *dst = (uint16_t *)backbuffer;
    for(int y = 0; y < height * 2; y+=2) {
      for(int x = 0; x < width; x++) {
        /*
        *dst = (src[0] & 0b11111000) << 8;
        *dst |= (src[1] & 0b11111100) << 3;
        *dst |= src[2] >> 3;
        *(dst + width) = *dst;
        */
        *(dst + width) = *dst = ((src[0] & 0b11111000) << 8) | ((src[1] & 0b11111100) << 3) | (src[2] >> 3);
        dst++;
        src += 4;
      }
      // Skip the vertically pixel-doubled row we set above
      dst += width;
    }

    gpio_put(dc, 0); // command mode
    gpio_put(cs, 0);
    write_blocking_parallel(&cmd, 1);
    gpio_put(dc, 1); // data mode
    dma_channel_set_trans_count(pd_st_dma, 160 * 240, false);
    dma_channel_set_read_addr(pd_st_dma, &backbuffer, true);

    //dma_channel_set_trans_count(pd_st_dma, width * height, false);
    //dma_channel_set_read_addr(pd_st_dma, &framebuffer, true);

    /*uint8_t *src = (uint8_t *)framebuffer;
    for(int y = 0; y < height; y++) {
      uint16_t *dst = linebuffer;
      for(int x = 0; x < width; x++) {
        *dst = ((src[0] & 0b11111000) << 8) | ((src[1] & 0b11111100) << 3) | (src[2] >> 3);
        *(dst + width) = *dst;
        dst++;
        src += 4;
      }
      dma_channel_wait_for_finish_blocking(pd_st_dma);
      dma_channel_set_trans_count(pd_st_dma, width * 2, false);
      dma_channel_set_read_addr(pd_st_dma, &linebuffer, true);
    }
    
    dma_channel_wait_for_finish_blocking(pd_st_dma);*/

    // This may cause a race between PIO and the
    // subsequent chipselect de-assert for the last pixel
    /*while(!pio_sm_is_tx_fifo_empty(parallel_pio, parallel_pd_sm))
      ;

    gpio_put(cs, 1);*/
  }

  void ST7789::set_backlight(uint8_t brightness) {
    // gamma correct the provided 0-255 brightness value onto a
    // 0-65535 range for the pwm counter
    float gamma = 2.8;
    uint16_t value = (uint16_t)(pow((float)(brightness) / 255.0f, gamma) * 65535.0f + 0.5f);
    pwm_set_gpio_level(bl, value);
    if(brightness == 0 && !display_sleep) {
      command(reg::SLPOUT);  // leave sleep mode
      sleep_ms(5);
      display_sleep = true;
    } else if (display_sleep) {
      command(reg::SLPOUT);  // leave sleep mode
      sleep_ms(120);
      display_sleep = false;
    }
  }
}
