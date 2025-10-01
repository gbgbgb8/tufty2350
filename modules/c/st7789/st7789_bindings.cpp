#include <cstdio>
#include "hardware/spi.h"
#include "hardware/sync.h"
#include "pico/binary_info.h"
#include "pico/stdlib.h"
#include <new>  // for placement new

#include "st7789.hpp"

using namespace pimoroni;

ST7789 *display = nullptr;

#define MP_OBJ_TO_PTR2(o, t) ((t *)(uintptr_t)(o))
#define m_new_class(cls, ...) new(m_new(cls, 1)) cls(__VA_ARGS__)
#define m_del_class(cls, ptr) ptr->~cls();m_del(cls, ptr, 1)

extern "C" {
#include "st7789_bindings.h"
#include "py/builtin.h"

typedef struct _ST7789_obj_t {
    mp_obj_base_t base;
} ST7789_obj_t;


mp_obj_t st7789_make_new(const mp_obj_type_t *type, size_t n_args, size_t n_kw, const mp_obj_t *all_args) {
    _ST7789_obj_t *self = mp_obj_malloc_with_finaliser(ST7789_obj_t, &ST7789_type);
    display = m_new_class(ST7789);
    return MP_OBJ_FROM_PTR(self);
}

mp_obj_t st7789___del__(mp_obj_t self_in) {
    (void)self_in;
    m_del_class(ST7789, display);
    display = nullptr;
    return mp_const_none;
}

mp_obj_t st7789_update(mp_obj_t self_in) {
    (void)self_in;
    display->update();
    return mp_const_none;
}

mp_obj_t st7789_set_backlight(mp_obj_t self_in, mp_obj_t value_in) {
    (void)self_in;
    display->set_backlight((uint8_t)(mp_obj_get_float(value_in) * 255));
    return mp_const_none;
}

mp_int_t st7789_get_framebuffer(mp_obj_t self_in, mp_buffer_info_t *bufinfo, mp_uint_t flags) {
    (void)self_in;
    (void)flags;
    bufinfo->buf = display->get_framebuffer();
    bufinfo->len = 160 * 120 * 4;
    bufinfo->typecode = 'B';
    return 0;
}

}