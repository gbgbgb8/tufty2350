import gc
import json
import os
import io as stream
import sys
import time
import random
import pcf85063a

import machine
import powman
import st7789
import builtins

import picovector

_CASE_LIGHTS = [machine.PWM(machine.Pin.board.CL0), machine.PWM(machine.Pin.board.CL1),
                machine.PWM(machine.Pin.board.CL2), machine.PWM(machine.Pin.board.CL3)]

for led in _CASE_LIGHTS:
    led.freq(500)


def set_case_led(led, value):
    if not isinstance(led, int):
        raise TypeError("LED must be a number between 0 and 3")

    if led < 0 or led > len(_CASE_LIGHTS) - 1:
        raise ValueError("LED out of range!")

    if not isinstance(value, (int, float)):
        raise TypeError("brightness must be a number between 0.0 and 1.0")

    if value < 0 or value > 1.0:
        raise ValueError("brightness must be between 0.0 and 1.0")

    value = int(value * 65535)
    _CASE_LIGHTS[led].duty_u16(value)


def get_case_led(led=None):

    if led is None:
        raise ValueError("LED must be provided!")

    if not isinstance(led, int):
        raise TypeError("LED must be a number between 0 and 3")

    if led < 0 or led > len(_CASE_LIGHTS) - 1:
        raise ValueError("LED out of range!")

    return _CASE_LIGHTS[led].duty_u16() / 65535


def get_light():
    # TODO: Returning the raw u16 is a little meh here, can we do an approx lux conversion?
    return LIGHT_SENSOR.read_u16()


def localtime_to_rtc():
    rtc.datetime(time.localtime())


def rtc_to_localtime():
    dt = rtc.datetime()
    machine.RTC().datetime((dt[0], dt[1], dt[2], dt[6], dt[3], dt[4], dt[5], 0))


def time_from_ntp():
    import ntptime

    ntptime.settime()
    del sys.modules["ntptime"]
    gc.collect()
    localtime_to_rtc()


# takes a text string (that may include newline characters) and performs word
# wrapping. returns a line of lines and their widths as a result.
def wrap_and_measure(image, text, size, max_width):
    result = []
    for line in text.splitlines():
        # if max_width is specified then perform word wrapping
        if max_width:
            # setup a start and end cursor to traverse the text
            start, end = 0, 0
            last_width = 0
            i = 0
            while True:
                i += 1
                # search for the next space
                end = line.find(" ", end)
                if end == -1:
                    end = len(line)

                # measure the text up to the space
                width, _ = image.measure_text(line[start:end], size)
                if width >= max_width:
                    # line exceeded max length
                    new_end = line.rfind(" ", start, end)
                    if new_end == -1:
                        result.append((line[start:end], last_width))
                        start = end + 1
                    else:
                        result.append((line[start:new_end], last_width))
                        start = new_end + 1
                elif end == len(line):
                    # reached the end of the string
                    result.append((line[start:end], width))
                    break

                # step past the last space
                end += 1
                last_width = width
        else:
            # no wrapping needed, just return the original line with its width
            width, _ = image.measure_text(line, size)
            result.append((line, width))

    return result


def clamp(v, vmin, vmax):
    return max(vmin, min(v, vmax))


def rnd(v1, v2=None):
    if v2:
      return random.randint(v1, v2)
    else:
      return random.randint(0, v1)

def frnd(v1, v2=None):
    if v2:
      return random.uniform(v1, v2)
    else:
      return random.uniform(0, v1)


def file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def is_dir(path):
    try:
        flags = os.stat(path)
        return flags[0] & 0x4000  # is a directory
    except:  # noqa: E722
        return False


class SpriteSheet:
    def __init__(self, file, columns, rows):
        self.image = image.load(file)
        self.sw = int(self.image.width / columns)
        self.sh = int(self.image.height / rows)

        self.sprites = []
        for x in range(columns):
            column = []
            for y in range(rows):
                sprite = self.image.window(self.sw * x, self.sh * y, self.sw, self.sh)
                column.append(sprite)
            self.sprites.append(column)

    def sprite(self, x, y):
        return self.sprites[x][y]

    def animation(self, x=0, y=0, count=None, horizontal=True):
        if not count:
            count = int(self.image.width / self.sw)
        return AnimatedSprite(self, x, y, count, horizontal)


class AnimatedSprite:
    def __init__(self, spritesheet, x, y, count, horizontal=True):
        self.spritesheet = spritesheet
        self.frames = []
        for _ in range(count):
            self.frames.append((x, y))
            if horizontal:
                x += 1
            else:
                y += 1

    def frame(self, frame_index=0):
        frame_index = int(frame_index)
        frame_index %= len(self.frames)
        return self.spritesheet.sprite(
            self.frames[frame_index][0], self.frames[frame_index][1]
        )

    def count(self):
        return len(self.frames)


# show the current free memory including the delta since last time the
# function was called, optionally include a custom message
_lf = None


def free(message=""):
    global _lf
    import gc

    gc.collect()  # collect any free memory before reporting
    f = int(gc.mem_free() / 1024)
    print(f"{message}: {f}kb", end="")
    if _lf:
        delta = f - _lf
        sign = "-" if delta < 0 else "+"
        print(f" ({sign}{abs(delta)}kb)", end="")
    print("")
    _lf = f


def woken_by_button():
    return powman.get_wake_reason() in (
        powman.WAKE_BUTTON_A,
        powman.WAKE_BUTTON_B,
        powman.WAKE_BUTTON_C,
        powman.WAKE_BUTTON_UP,
        powman.WAKE_BUTTON_DOWN,
    )


def pressed_to_wake(button):
    # TODO: BUTTON_HOME cannot be a wake button
    # so maybe raise an exception
    return button in powman.get_wake_buttons()


def woken_by_reset():
    return powman.get_wake_reason() == 255


def sleep():
    display.set_backlight(0)
    powman.sleep()


class Assets:
    @staticmethod
    def font(name):
        file = f"{ASSETS}/fonts/{name}.ppf"
        try:
            return pixel_font.load(file)
        except OSError as e:
            raise ValueError(f'Font "{name}" not found. (Missing {file}?)') from e

    @staticmethod
    def fonts():
        return [f[:-4] for f in os.listdir(f"{ASSETS}/fonts") if f.endswith(".ppf")]


def is_charging():
    # We only want to return the charge status if the USB cable is connected.
    if VBUS_DETECT.value():
        return not CHARGE_STAT.value()

    return False


def get_usb_connected():
    return bool(VBUS_DETECT.value())


def sample_adc_u16(adc, samples=1):
    val = []
    for _ in range(samples):
        val.append(adc.read_u16())
    return sum(val) / len(val)


def get_battery_level():
    # Use the battery voltage to estimate the remaining percentage

    # Get the average reading over 20 samples from our VBAT and VREF
    voltage = sample_adc_u16(VBAT_SENSE, 10) * conversion_factor * 2
    vref = sample_adc_u16(SENSE_1V1, 10) * conversion_factor
    voltage = voltage / vref * 1.1

    # Return the battery level as a percentage
    return min(100, max(0, round(123 - (123 / pow((1 + pow((voltage / 3.2), 80)), 0.165)))))


def get_battery_level():
    # Use the battery voltage to estimate the remaining percentage

    # Get the average reading over 20 samples from our VBAT and VREF
    voltage = sample_adc_u16(VBAT_SENSE, 10) * conversion_factor * 2
    vref = sample_adc_u16(SENSE_1V1, 10) * conversion_factor
    voltage = voltage / vref * 1.1

    # Return the battery level as a percentage
    return min(100, max(0, round(123 - (123 / pow((1 + pow((voltage / 3.2), 80)), 0.165)))))


def get_disk_usage(mountpoint="/"):
    # f_bfree and f_bavail should be the same?
    # f_files, f_ffree, f_favail and f_flag are unsupported.
    f_bsize, f_frsize, f_blocks, f_bfree, _, _, _, _, _, f_namemax = os.statvfs(
        mountpoint
    )

    f_total_size = f_frsize * f_blocks
    f_total_free = f_bsize * f_bfree
    f_total_used = f_total_size - f_total_free

    f_used = 100 / f_total_size * f_total_used
    f_free = 100 / f_total_size * f_total_free

    return f_total_size, f_used, f_free


class State:
    @staticmethod
    def delete(app):
        try:
            os.remove("/state/{}.json".format(app))
        except OSError:
            pass

    @staticmethod
    def save(app, data):
        try:
            with open("/state/{}.json".format(app), "w") as f:
                f.write(json.dumps(data))
                f.flush()
        except OSError:
            import os

            try:
                os.stat("/state")
            except OSError:
                os.mkdir("/state")
                State.save(app, data)

    @staticmethod
    def modify(app, data):
        state = {}
        State.load(app, state)
        state.update(data)
        State.save(app, state)

    @staticmethod
    def load(app, defaults):
        try:
            data = json.loads(open("/state/{}.json".format(app), "r").read())
            if type(data) is dict:
                defaults.update(data)
                return True
        except (OSError, ValueError):
            pass

        State.save(app, defaults)
        return False


def mode(mode):
    global _current_mode

    if mode == _current_mode:
        return False

    _current_mode = mode

    # TODO: Mutate the existing screen object?
    font = screen.font
    brush = screen.pen
    resolution = (320, 240) if HIRES else (160, 120)
    setattr(builtins, "screen", image(*resolution, memoryview(display)))
    screen.font = font if font is not None else DEFAULT_FONT
    screen.pen = brush if brush is not None else BG
    picovector.default_target = screen

    return True


def run(update, init=None, on_exit=None, auto_clear=True):
    screen.font = DEFAULT_FONT
    screen.clear(BG)
    screen.pen = FG
    try:
        if init:
            init()
        try:
            while True:
                if auto_clear:
                    screen.clear(BG)
                    screen.pen = FG
                io.poll()
                if (result := update()) is not None:
                    return result
                gc.collect()
                display.update(screen.width == 320)
        except KeyboardInterrupt:
            pass
        finally:
            if on_exit:
                on_exit()

    except Exception as e:  # noqa: BLE001
        warning("Error!", get_exception(e))


def get_exception(e):
    s = stream.StringIO()
    sys.print_exception(e, s)
    s.seek(0)
    s.readline()  # Drop the "Traceback" bit
    return s.read()


# Draw an overlay box with a given message within it
def message(title, text, window=None):
    error_window = window or screen.window(0, 0, screen.width, screen.height)
    error_window.font = DEFAULT_FONT

    # Draw a light grey background
    background = shape.rounded_rectangle(
        0, 0, error_window.width, error_window.height, 5, 5, 5, 5
    )
    heading = shape.rounded_rectangle(0, 0, error_window.width, 12, 5, 5, 0, 0)
    error_window.pen = color.rgb(100, 100, 100, 200)
    error_window.shape(background)

    error_window.pen = color.rgb(255, 100, 100, 200)
    error_window.shape(heading)

    error_window.pen = color.rgb(50, 100, 50)
    tw = 35
    error_window.shape(
        shape.rounded_rectangle(
            error_window.width - tw - 10, error_window.height - 12, tw, 12, 3, 3, 0, 0
        )
    )

    error_window.pen = color.rgb(255, 200, 200)
    error_window.text(
        "Okay", error_window.width - tw + 5 - 10, error_window.height - 12
    )
    y = 0
    error_window.text(title, 5, y)
    y += 17

    error_window.pen = color.rgb(200, 200, 200)
    text_lines = wrap_and_measure(error_window, text, 12, error_window.width - 10)
    for line, _width in text_lines:
        error_window.text(line, 5, y)
        y += 10

    display.update(screen.width == 320)
    while True:
        io.poll()
        if io.pressed:
            break
    while io.pressed:
        io.poll()


def warning(title, text):
    print(f"- ERROR: {text}")
    message(title, text)


def load_font(font_file):
    try:
        return pixel_font.load(font_file)
    except OSError:
        return pixel_font.load(f"/rom/fonts/{font_file}.ppf")


class ROMFonts:
    def __getattr__(self, key):
        try:
            return pixel_font.load(f"/rom/fonts/{key}.ppf")
        except OSError:
            raise AttributeError(f"Font {key} not found!")

    def __dir__(self):
        return [f[:-4] for f in os.listdir("/rom/fonts") if f.endswith(".ppf")]


rom_font = ROMFonts()

# RTC
rtc = pcf85063a.PCF85063A(machine.I2C())

if time.localtime()[0] >= 2025:
    localtime_to_rtc()

elif rtc.datetime()[0] >= 2025:
    rtc_to_localtime()


display = st7789.ST7789()

# Import PicoSystem module constants to builtins,
# so they are available globally.
for k, v in picovector.__dict__.items():
    if not k.startswith("__"):
        setattr(builtins, k, v)

setattr(builtins, "screen", image(160, 120, memoryview(display)))
picovector.default_target = screen


ASSETS = "/system/assets"
LIGHT_SENSOR = machine.ADC(machine.Pin("LIGHT_SENSE"))
DEFAULT_FONT = rom_font.sins
ERROR_FONT = rom_font.desert

FG = color.rgb(255, 255, 255)
BG = color.rgb(20, 40, 60)

VBAT_SENSE = machine.ADC(machine.Pin.board.VBAT_SENSE)
VBUS_DETECT = machine.Pin.board.VBUS_DETECT
CHARGE_STAT = machine.Pin.board.CHARGE_STAT
SENSE_1V1 = machine.ADC(machine.Pin.board.SENSE_1V1)

BAT_MAX = 4.10
BAT_MIN = 3.00

HIRES = 1
LORES = 0

conversion_factor = 3.3 / 65536

_current_mode = LORES


# Build in some badgeware helpers, so we don't have to "bw.lores" etc
for k in ("mode", "HIRES", "LORES", "SpriteSheet", "load_font", "rom_font"):
    setattr(builtins, k, locals()[k])


# Finally, build in badgeware as "bw" for less frequently used things
setattr(builtins, "bw", sys.modules["badgeware"])


if __name__ == "__main__":
    warning("Hello from badgeware.py", "Why are you running me?")
