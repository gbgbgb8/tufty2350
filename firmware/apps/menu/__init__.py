import os
import sys

sys.path.insert(0, "/system/apps/menu")
os.chdir("/system/apps/menu")

import math

import ui
from badgeware import (Image, PixelFont, SpriteSheet, brushes, file_exists, io,
                       is_dir, run, screen, shapes)
from icon import Icon

# screen.antialias = Image.X4

# define the list of installed apps
#
# - hack them!
# - replace them with your own
# - reorder them
# - what would mona do...?
apps = [
    ("Christmas Countdown", "christmas"),
    ("Snarky Sciuridae", "badgepet"),
    ("Sketchy Sketch", "sketch"),
    ("Plucky Cluck", "pluckycluck"),
    ("Hydrate", "hydrate"),
    ("Bee Amaze'd", "bee_amazed"),
]

mona = SpriteSheet("/system/assets/mona-sprites/mona-default.png", 11, 1)
screen.font = PixelFont.load("/system/assets/fonts/ark.ppf")
# screen.antialias = Image.X2

# find installed apps and create icons
icons = []
for app in apps:
    name, path = app[0], app[1]

    if is_dir(f"/system/apps/{path}"):
        if file_exists(f"/system/apps/{path}/icon.png"):
            x = len(icons) % 3
            y = math.floor(len(icons) / 3)
            pos = (x * 48 + 32, y * 48 + 42)
            sprite = Image.load(f"/system/apps/{path}/icon.png")
            icons.append(Icon(pos, name, len(icons), sprite))

active = 0

MAX_ALPHA = 255
alpha = 30


def update():
    global active, icons, alpha

    # process button inputs to switch between icons
    if io.BUTTON_C in io.pressed:
        active += 1
    if io.BUTTON_A in io.pressed:
        active -= 1
    if io.BUTTON_UP in io.pressed:
        active -= 3
    if io.BUTTON_DOWN in io.pressed:
        active += 3
    if io.BUTTON_B in io.pressed:
        return f"/system/apps/{apps[active][1]}"

    active %= len(icons)

    ui.draw_background()
    ui.draw_header()

    # draw menu icons
    for i in range(len(icons)):
        icons[i].activate(active == i)
        icons[i].draw()

    # draw label for active menu icon
    if Icon.active_icon:
        label = f"{Icon.active_icon.name}"
        w, _ = screen.measure_text(label)
        screen.brush = ui.phosphor
        screen.draw(shapes.rounded_rectangle(80 - (w / 2) - 4, 100, w + 8, 15, 4))
        screen.brush = brushes.color(20, 40, 60)
        screen.text(label, 80 - (w / 2), 101)

    if alpha <= MAX_ALPHA:
        screen.brush = brushes.color(0, 0, 0, 255 - alpha)
        screen.clear()
        alpha += 30

    return None


if __name__ == "__main__":
    run(update)
