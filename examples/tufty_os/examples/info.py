# ICON info
# NAME Info
# DESC Tufty 2350 Specification & Info

import tufty2350
import version
from tufty2350 import WIDTH
from picovector import ANTIALIAS_BEST, PicoVector, Polygon, Transform

TEXT_SIZE = 1
LINE_HEIGHT = 15

version = version.BUILD

display = tufty2350.Tufty2350()
display.led(128)

# Pico Vector
vector = PicoVector(display.display)
vector.set_antialiasing(ANTIALIAS_BEST)
t = Transform()

TITLE_BAR = Polygon()
TITLE_BAR.rectangle(2, 2, 260, 16, (8, 8, 8, 8))
TITLE_BAR.circle(253, 10, 4)

TEXT_BOX = Polygon()
TEXT_BOX.rectangle(2, 30, 260, 125, (8, 8, 8, 8))

# Clear to white
display.set_pen(15)
display.clear()

display.set_font("bitmap8")
display.set_pen(0)
vector.draw(TITLE_BAR)
display.set_pen(15)
display.text("tuftyOS", 7, 6, WIDTH, 1.0)
display.text("info", WIDTH - 40, 6, WIDTH, 1)

display.set_pen(2)
vector.draw(TEXT_BOX)

display.set_pen(1)

y = 32 + int(LINE_HEIGHT / 2)

display.text("Made by Pimoroni, powered by MicroPython", 5, y, WIDTH, TEXT_SIZE)
y += LINE_HEIGHT
display.text("Dual-core RP2350, Up to 150MHz with 520KB of SRAM", 5, y, WIDTH, TEXT_SIZE)
y += LINE_HEIGHT
display.text("4MB of QSPI flash", 5, y, WIDTH, TEXT_SIZE)
y += LINE_HEIGHT
display.text("264x176 pixel Black/White e-Ink", 5, y, WIDTH, TEXT_SIZE)
y += LINE_HEIGHT
display.text("For more info:", 5, y, WIDTH, TEXT_SIZE)
y += LINE_HEIGHT
display.text("https://pimoroni.com/tufty2350", 5, y, WIDTH, TEXT_SIZE)
y += LINE_HEIGHT
display.text(f"\nTuftyOS OS {version}", 5, y, WIDTH, TEXT_SIZE)

display.update()

# Call halt in a loop, on battery this switches off power.
# On USB, the app will exit when A+C is pressed because the launcher picks that up.

while True:
    display.keepalive()
    display.halt()
