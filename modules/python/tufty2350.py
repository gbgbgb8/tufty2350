import machine
from picographics import PicoGraphics, DISPLAY_EXPLORER
import cppmem
import powman

BUTTON_DOWN = 11
BUTTON_A = 12
BUTTON_B = 13
BUTTON_C = 14
BUTTON_UP = 15
BUTTON_USER = 22

BUTTON_MASK = 0b11111 << 11

SYSTEM_VERY_SLOW = 0
SYSTEM_SLOW = 1
SYSTEM_NORMAL = 2
SYSTEM_FAST = 3
SYSTEM_TURBO = 4

LED = 8
SENSOR_POWER = 9
LIGHT_SENSE_ADC = 43

WIDTH = 320
HEIGHT = 240

SYSTEM_FREQS = [
    4000000,
    12000000,
    48000000,
    133000000,
    250000000
]

BUTTONS = {
    BUTTON_DOWN: machine.Pin(BUTTON_DOWN, machine.Pin.IN, machine.Pin.PULL_UP),
    BUTTON_A: machine.Pin(BUTTON_A, machine.Pin.IN, machine.Pin.PULL_UP),
    BUTTON_B: machine.Pin(BUTTON_B, machine.Pin.IN, machine.Pin.PULL_UP),
    BUTTON_C: machine.Pin(BUTTON_C, machine.Pin.IN, machine.Pin.PULL_UP),
    BUTTON_UP: machine.Pin(BUTTON_UP, machine.Pin.IN, machine.Pin.PULL_UP),
}

LIGHT_POWER = machine.Pin(SENSOR_POWER, machine.Pin.OUT)
LIGHT_SENSOR = machine.ADC(machine.Pin(LIGHT_SENSE_ADC))

cppmem.set_mode(cppmem.MICROPYTHON)


def is_wireless():
    return True


def woken_by_button():
    return powman.get_wake_reason() in [0, 1, 2]


def pressed_to_wake(button):
    try:
        return [12, 13, 14].index(button) == powman.get_wake_reason()
    except ValueError:
        raise KeyError("Button not valid for device wake function!") from None


def woken_by_reset():
    return powman.get_wake_reason() == 255


def system_speed(speed):
    try:
        machine.freq(SYSTEM_FREQS[speed])
    except IndexError:
        pass


class Tufty2350():
    def __init__(self):
        self.display = PicoGraphics(DISPLAY_EXPLORER, rotate=180)
        self._led = machine.PWM(machine.Pin(LED))
        self._led.freq(1000)
        self._led.duty_u16(0)

    def __getattr__(self, item):
        # Glue to redirect calls to PicoGraphics
        return getattr(self.display, item)

    def update(self):
        self.display.update()

    def led(self, brightness):
        brightness = max(0, min(255, brightness))
        self._led.duty_u16(int(brightness * 256))

    def invert(self, _invert):
        raise RuntimeError("Display invert not supported in PicoGraphics.")

    def thickness(self, _thickness):
        raise RuntimeError("Thickness not supported in PicoGraphics.")

    def pressed(self, button):
        return BUTTONS[button].value() == 0

    def pressed_any(self):
        for button in BUTTONS.values():
            if button.value() == 0:
                return True
        return False

    def sleep(self):
        self.display.set_backlight(0)
        powman.goto_dormant_until_pin(None, False, False)

    def get_light(self):
        LIGHT_POWER.value(1)
        reading = LIGHT_SENSOR.read_u16()
        LIGHT_POWER.value(0)

        return reading
