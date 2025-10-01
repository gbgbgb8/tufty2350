#pragma once

#include "hardware/spi.h"
#include "hardware/dma.h"
#include "hardware/gpio.h"
#include "hardware/pio.h"
#include "hardware/pwm.h"
#include "hardware/clocks.h"
#include "pico/stdlib.h"


#ifndef NO_QSTR
#include "st7789_parallel.pio.h"
#endif

#include <algorithm>


namespace pimoroni {
  class ST7789 {
  private:
    int width = 160;
    int height = 120;

    // interface pins
    uint cs = 27;
    uint dc = 28;
    uint wr_sck = 30;
    uint rd_sck = 31;
    uint d0 = 32;
    uint bl = 26;
  
    // pio stuff
    PIO parallel_pio = pio1;
  
    // Regular commands
    uint parallel_sm;
    int parallel_offset;
    uint st_dma;

    // Pixel double
    uint parallel_pd_sm;
    int parallel_pd_offset;
    uint pd_st_dma;

    // LCD state tracking
    bool display_on = false;
    bool display_sleep = true;

  public:
    // Parallel init
    ST7789() {
      pio_set_gpio_base(parallel_pio, d0 + 8 >= 32 ? 16 : 0);

      parallel_sm = pio_claim_unused_sm(parallel_pio, true);
      parallel_offset = pio_add_program(parallel_pio, &st7789_parallel_program);
      if(parallel_offset == -1) {
        panic("Could not add parallel PIO program.");
      }

      parallel_pd_sm = pio_claim_unused_sm(parallel_pio, true);
      parallel_pd_offset = pio_add_program(parallel_pio, &st7789_parallel_pd_program);
      if(parallel_offset == -1) {
        panic("Could not add parallel pixel-doubling PIO program.");
      }

      pio_gpio_init(parallel_pio, wr_sck);

      gpio_set_function(rd_sck,  GPIO_FUNC_SIO);
      gpio_set_dir(rd_sck, GPIO_OUT);

      for(auto i = 0u; i < 8; i++) {
        pio_gpio_init(parallel_pio, d0 + i);
      }

      pio_sm_set_consecutive_pindirs(parallel_pio, parallel_sm, d0, 8, true);
      pio_sm_set_consecutive_pindirs(parallel_pio, parallel_sm, wr_sck, 1, true);

      // Is this needed?
      pio_sm_set_consecutive_pindirs(parallel_pio, parallel_pd_sm, d0, 8, true);
      pio_sm_set_consecutive_pindirs(parallel_pio, parallel_pd_sm, wr_sck, 1, true);

      pio_sm_config pd_c = st7789_parallel_pd_program_get_default_config(parallel_pd_offset);
      sm_config_set_out_pins(&pd_c, d0, 8);
      sm_config_set_sideset_pins(&pd_c, wr_sck);
      sm_config_set_fifo_join(&pd_c, PIO_FIFO_JOIN_TX);
      sm_config_set_out_shift(&pd_c, false, false, 16);
      //sm_config_set_in_shift(&pd_c, false, false, 32);

      pio_sm_config c = st7789_parallel_program_get_default_config(parallel_offset);
      sm_config_set_out_pins(&c, d0, 8);
      sm_config_set_sideset_pins(&c, wr_sck);
      sm_config_set_fifo_join(&c, PIO_FIFO_JOIN_TX);
      sm_config_set_out_shift(&c, false, true, 8);

      // Determine clock divider
      constexpr uint32_t max_pio_clk = 64 * MHZ;
      const uint32_t sys_clk_hz = clock_get_hz(clk_sys);
      const uint32_t clk_div = (sys_clk_hz + max_pio_clk - 1) / max_pio_clk;

      sm_config_set_clkdiv(&pd_c, clk_div);
      sm_config_set_clkdiv(&c, clk_div);

      pio_sm_init(parallel_pio, parallel_pd_sm, parallel_pd_offset, &pd_c);
      pio_sm_set_enabled(parallel_pio, parallel_pd_sm, true);

      pio_sm_init(parallel_pio, parallel_sm, parallel_offset, &c);
      pio_sm_set_enabled(parallel_pio, parallel_sm, true);


      st_dma = dma_claim_unused_channel(true);
      dma_channel_config config = dma_channel_get_default_config(st_dma);
      channel_config_set_transfer_data_size(&config, DMA_SIZE_8);
      channel_config_set_bswap(&config, false);
      channel_config_set_dreq(&config, pio_get_dreq(parallel_pio, parallel_sm, true));
      dma_channel_configure(st_dma, &config, &parallel_pio->txf[parallel_sm], NULL, 0, false);

      pd_st_dma = dma_claim_unused_channel(true);
      dma_channel_config pd_config = dma_channel_get_default_config(pd_st_dma);
      channel_config_set_transfer_data_size(&pd_config, DMA_SIZE_16);
      channel_config_set_bswap(&pd_config, false);
      channel_config_set_dreq(&pd_config, pio_get_dreq(parallel_pio, parallel_pd_sm, true));
      dma_channel_configure(pd_st_dma, &pd_config, &parallel_pio->txf[parallel_pd_sm], NULL, 0, false);

      gpio_put(rd_sck, 1);

      init();
    }

    ~ST7789() {
      if(dma_channel_is_claimed(st_dma)) {
        dma_channel_abort(st_dma);
        dma_channel_unclaim(st_dma);
      }
      if(dma_channel_is_claimed(pd_st_dma)) {
        dma_channel_abort(pd_st_dma);
        dma_channel_unclaim(pd_st_dma);
      }

      if(pio_sm_is_claimed(parallel_pio, parallel_sm)) {
        pio_sm_set_enabled(parallel_pio, parallel_sm, false);
        pio_sm_drain_tx_fifo(parallel_pio, parallel_sm);
        //pio_sm_unclaim(parallel_pio, parallel_sm);
        pio_remove_program_and_unclaim_sm(&st7789_parallel_program, parallel_pio, parallel_sm, parallel_offset);
      }
      if(pio_sm_is_claimed(parallel_pio, parallel_pd_sm)) {
        pio_sm_set_enabled(parallel_pio, parallel_pd_sm, false);
        pio_sm_drain_tx_fifo(parallel_pio, parallel_pd_sm);
        //pio_sm_unclaim(parallel_pio, parallel_pd_sm);
        pio_remove_program_and_unclaim_sm(&st7789_parallel_pd_program, parallel_pio, parallel_pd_sm, parallel_pd_offset);
      }
    }

    void update();
    void set_backlight(uint8_t brightness);
    uint32_t *get_framebuffer();

  private:
    void init();
    void write_blocking_dma(const uint8_t *src, size_t len);
    void write_blocking_parallel(const uint8_t *src, size_t len);
    void write_blocking_parallel_pixel_doubled(const uint8_t *src, size_t len);
    void command(uint8_t command, size_t len = 0, const char *data = NULL);
  };

}
