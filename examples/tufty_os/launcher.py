import gc
import math
import os
import time

import tufty2350
from picovector import (ANTIALIAS_BEST, HALIGN_CENTER, PicoVector, Polygon,
                        Transform)

import tufty_os

ICONS = {
    "badge": "\uea67",
    "book_2": "\uf53e",
    "cloud": "\ue2bd",
    "description": "\ue873",
    "help": "\ue887",
    "wifi": "\ue63e",
    "image": "\ue3f4",
    "info": "\ue88e",
    "format_list_bulleted": "\ue241",
    "joystick": "\uf5ee"
}

APP_DIR = "/examples"
FONT_SIZE = 1

changed = False
exited_to_launcher = False
woken_by_button = tufty2350.woken_by_button()  # Must be done before we clear_pressed_to_wake


if tufty2350.pressed_to_wake(tufty2350.BUTTON_A) and tufty2350.pressed_to_wake(tufty2350.BUTTON_C):
    # Pressing A and C together at start quits app
    exited_to_launcher = tufty_os.state_clear_running()
    tufty2350.reset_pressed_to_wake()
else:
    # Otherwise restore previously running app
    tufty_os.state_launch()


display = tufty2350.Tufty2350()
display.set_font("bitmap8")
display.led(0)

BG = display.create_pen(195, 195, 195)

# Pico Vector
vector = PicoVector(display.display)
vector.set_antialiasing(ANTIALIAS_BEST)
t = Transform()
vector.set_font("Roboto-Medium-With-Material-Symbols.af", 20)
vector.set_font_align(HALIGN_CENTER)
vector.set_transform(t)

TITLE_BAR = Polygon()
TITLE_BAR.rectangle(2, 2, 260, 16, (8, 8, 8, 8))
TITLE_BAR.circle(253, 10, 4)

SELECTED_BORDER = Polygon()
SELECTED_BORDER.rectangle(0, 0, 90, 90, (10, 10, 10, 10), 5)

state = {
    "page": 0,
    "running": "launcher"
}

tufty_os.state_load("launcher", state)

examples = [x[:-3] for x in os.listdir(APP_DIR) if x.endswith(".py")]

# Page layout
centers = [[45, 52], [126, 52], [209, 52], [45, 130], [126, 130], [209, 130]]

MAX_PAGE = math.ceil(len(examples) / 6)
MAX_PER_ROW = 3
MAX_PER_PAGE = MAX_PER_ROW * 2

WIDTH = 264

# index for the currently selected file on the page
selected_file = 1

# Number of icons on the current page
icons_total = 0


def map_value(input, in_min, in_max, out_min, out_max):
    return (((input - in_min) * (out_max - out_min)) / (in_max - in_min)) + out_min


def draw_disk_usage(x):
    _, f_used, _ = tufty_os.get_disk_usage()

    display.set_pen(15)
    display.image(
        bytearray(
            (
                0b00000000,
                0b00111100,
                0b00111100,
                0b00111100,
                0b00111000,
                0b00000000,
                0b00000000,
                0b00000001,
            )
        ),
        8,
        8,
        x,
        6,
    )
    display.rectangle(x + 10, 5, 45, 10)
    display.set_pen(0)
    display.rectangle(x + 11, 6, 43, 8)
    display.set_pen(15)
    display.rectangle(x + 12, 7, int(41 / 100.0 * f_used), 6)


def render():
    global icons_total
    global selected_file

    display.set_pen(BG)
    display.clear()
    display.set_pen(0)

    icons_total = min(6, len(examples[(state["page"] * 6):]))

    for i in range(icons_total):
        x = centers[i][0]
        y = centers[i][1]

        label = examples[i + (state["page"] * 6)]
        file = f"{APP_DIR}/{label}.py"

        name = label
        icon = Polygon()

        with open(file) as f:
            header = [f.readline().strip() for _ in range(3)]

        for line in header:
            if line.startswith("# ICON "):
                icon = line[7:].strip()
                icon = ICONS[icon]

            if line.startswith("# NAME "):
                name = line[7:]

        vector.set_font_size(20)
        vector.set_transform(t)
        vector.text(icon, x, y)
        t.translate(x, y)
        t.scale(0.8, 0.8)
        # Snap to the last icon if the position isn't available.
        selected_file = min(selected_file, icons_total - 1)

        if selected_file == i:
            display.set_pen(1)
            t.translate(-45, -36)
            t.scale(1.0, 1.0)
            vector.draw(SELECTED_BORDER)
        t.reset()

        display.set_pen(0)
        vector.set_font_size(16)
        w = vector.measure_text(name)[2]
        vector.text(name, int(x - (w / 2)), y + 35)

    for i in range(MAX_PAGE):
        x = 253
        y = int((176 / 2) - (MAX_PAGE * 10 / 2) + (i * 10))
        display.set_pen(0)
        display.rectangle(x, y, 8, 8)
        if state["page"] != i:
            display.set_pen(3)
            display.rectangle(x + 1, y + 1, 6, 6)

    display.set_pen(0)
    vector.draw(TITLE_BAR)

    draw_disk_usage(100)

    display.set_pen(3)
    vector.set_font_size(14)
    vector.text("TuftyOS", 7, 14)

    display.update()


def wait_for_user_to_release_buttons():
    while display.pressed_any():
        time.sleep(0.01)


def launch_example(index):
    wait_for_user_to_release_buttons()

    file = examples[index]
    file = f"{APP_DIR}/{file}"

    for k in locals().keys():
        if k not in ("gc", "file", "tufty_os"):
            del locals()[k]

    gc.collect()

    tufty_os.launch(file)


def button(pin):
    global changed
    global selected_file
    global icons_total
    changed = True

    if pin == tufty2350.BUTTON_A:
        if (selected_file % MAX_PER_ROW) > 0:
            selected_file -= 1

    if pin == tufty2350.BUTTON_B:
        launch_example((state["page"] * MAX_PER_PAGE) + selected_file)

    if pin == tufty2350.BUTTON_C:
        if (selected_file % MAX_PER_ROW) < MAX_PER_ROW - 1:
            selected_file += 1

    if pin == tufty2350.BUTTON_UP:
        if selected_file >= MAX_PER_ROW:
            selected_file -= MAX_PER_ROW
        else:
            state["page"] = (state["page"] - 1) % MAX_PAGE
            selected_file += MAX_PER_ROW

    if pin == tufty2350.BUTTON_DOWN:
        if selected_file < MAX_PER_ROW and icons_total > MAX_PER_ROW:
            selected_file += MAX_PER_ROW
        elif selected_file >= MAX_PER_ROW or icons_total < MAX_PER_ROW + 1:
            state["page"] = (state["page"] + 1) % MAX_PAGE
            selected_file %= MAX_PER_ROW


if exited_to_launcher or not woken_by_button:
    wait_for_user_to_release_buttons()
    display.set_update_speed(tufty2350.UPDATE_MEDIUM)
    render()

display.set_update_speed(tufty2350.UPDATE_TURBO)

render()

while True:
    # Sometimes a button press or hold will keep the system
    # powered *through* HALT, so latch the power back on.
    # display.keepalive()

    if display.pressed(tufty2350.BUTTON_A):
        button(tufty2350.BUTTON_A)
    if display.pressed(tufty2350.BUTTON_B):
        button(tufty2350.BUTTON_B)
    if display.pressed(tufty2350.BUTTON_C):
        button(tufty2350.BUTTON_C)

    if display.pressed(tufty2350.BUTTON_UP):
        button(tufty2350.BUTTON_UP)
    if display.pressed(tufty2350.BUTTON_DOWN):
        button(tufty2350.BUTTON_DOWN)

    if changed:
        tufty_os.state_save("launcher", state)
        changed = False
        render()

    display.halt()
