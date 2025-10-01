#include "st7789_bindings.h"

/***** Module Functions *****/

static MP_DEFINE_CONST_FUN_OBJ_1(st7789___del___obj, st7789___del__);
static MP_DEFINE_CONST_FUN_OBJ_1(st7789_update_obj, st7789_update);
static MP_DEFINE_CONST_FUN_OBJ_2(st7789_set_backlight_obj, st7789_set_backlight);

/* Class Methods */
static const mp_rom_map_elem_t st7789_locals[] = {
    { MP_ROM_QSTR(MP_QSTR___del__), MP_ROM_PTR(&st7789___del___obj) },
    { MP_ROM_QSTR(MP_QSTR_update), MP_ROM_PTR(&st7789_update_obj) },
    { MP_ROM_QSTR(MP_QSTR_backlight), MP_ROM_PTR(&st7789_set_backlight_obj) },
};
static MP_DEFINE_CONST_DICT(mp_module_st7789_locals, st7789_locals);

MP_DEFINE_CONST_OBJ_TYPE(
    ST7789_type,
    MP_QSTR_ST7789,
    MP_TYPE_FLAG_NONE,
    make_new, st7789_make_new,
    buffer, st7789_get_framebuffer,
    locals_dict, (mp_obj_dict_t*)&mp_module_st7789_locals
);

/* Module Globals */
static const mp_map_elem_t st7789_globals[] = {
    { MP_OBJ_NEW_QSTR(MP_QSTR___name__), MP_OBJ_NEW_QSTR(MP_QSTR_st7789) },
    { MP_OBJ_NEW_QSTR(MP_QSTR_ST7789), (mp_obj_t)&ST7789_type },
    { MP_ROM_QSTR(MP_QSTR_WIDTH), MP_ROM_INT(160) },
    { MP_ROM_QSTR(MP_QSTR_HEIGHT), MP_ROM_INT(120) },
};
static MP_DEFINE_CONST_DICT(mp_module_st7789_globals, st7789_globals);

const mp_obj_module_t st7789_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t*)&mp_module_st7789_globals,
};

void mp_module_attr(mp_obj_t self_in, qstr attr, mp_obj_t *dest) {
    if (dest[0] == MP_OBJ_NULL && attr == MP_QSTR_test) {
        mp_printf(&mp_plat_print, "Hello Attr: %s\n", qstr_str(attr));
        dest[0] = mp_const_true;
    }
}

MP_REGISTER_MODULE(MP_QSTR_st7789, st7789_user_cmodule);
MP_REGISTER_MODULE_DELEGATION(st7789_user_cmodule, mp_module_attr);
