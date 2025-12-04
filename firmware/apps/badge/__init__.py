import sys
import os
import math
from badgeware import run, WIDTH, HEIGHT, clamp

sys.path.insert(0, "/system/apps/badge")
os.chdir("/system/apps/badge")


CX = WIDTH / 2
CY = HEIGHT / 2

screen.antialias = screen.X2

# details to be shown on the card
id_photo = Image.load("avatar.png")
id_name = "Your Name"
id_role = "Job title"

# see the 'assets/social' folder to see what's supported
id_socials = {"bluesky": {"icon": None, "handle": ""},
              "instagram": {"icon": None, "handle": ""},
              "github": {"icon": None, "handle": ""},
              "discord": {"icon": None, "handle": ""}
              }

# load in the social icons
for key in id_socials.keys():
    id_socials[key]["icon"] = Image.load(f"assets/socials/{key}.png")

# id card variables
id_body = shapes.rounded_rectangle(0, 0, 140, 100, 7)
id_outline = shapes.rounded_rectangle(0, 0, 140, 100, 7).stroke(2)
hue = 0.0
saturation = 0.0
background = brushes.color(255, 255, 255)
flip = False
flip_start = 0
rear_view = False
card_pos = (10, 10)

small_font = PixelFont.load("/system/assets/fonts/winds.ppf")
large_font = PixelFont.load("/system/assets/fonts/nope.ppf")


# Source - https://stackoverflow.com/a
# Posted by Tcll, modified by community. See post 'Timeline' for change history
# Retrieved 2025-12-04, License - CC BY-SA 4.0

scalar = 1.0


def hsv_to_rgb(h: scalar, s: scalar, v: scalar, a: scalar) -> tuple:
    a = int(255 * a)
    if s:
        if h == 1.0:
            h = 0.0
        i = int(h * 6.0)
        f = h * 6.0 - i

        w = int(255 * (v * (1.0 - s)))
        q = int(255 * (v * (1.0 - s * f)))
        t = int(255 * (v * (1.0 - s * (1.0 - f))))
        v = int(255 * v)

        if i == 0:
            return (v, t, w, a)
        if i == 1:
            return (q, v, w, a)
        if i == 2:
            return (w, v, t, a)
        if i == 3:
            return (w, q, v, a)
        if i == 4:
            return (t, w, v, a)
        if i == 5:
            return (v, w, q, a)
    else:
        v = int(255 * v)
        return (v, v, v, a)


def draw_background():
    # ripple effect background
    cy = CY - 8
    cx = CX

    y = 0
    for row in range(12):
        x = 0
        for col in range(16):
            dist = math.sqrt((x + 5 - cx) ** 2 + (y + 5 - cy) ** 2)
            pulse = (math.sin(-io.ticks / 400 + (dist / 6)) / 2) + 0.5
            pulse = 0.8 + (pulse / 2)
            screen.brush = brushes.color(0, 0, 0, 100 * pulse)
            screen.rectangle(x, y, 10, 10)
            x += 10
        y += 10


def shadow_text(text, x, y):
    screen.brush = brushes.color(20, 40, 60, 100)
    screen.text(text, x + 1, y + 1)
    screen.brush = brushes.color(0, 0, 0)
    screen.text(text, x, y)


def center_text(text, y):
    w, _ = screen.measure_text(text)
    shadow_text(text, 80 - (w / 2), y)


def init():
    pass


def change_background(h=None, s=None):
    # a little helper to change the background color
    global background, hue, saturation

    if h:
        hue += h
        hue = hue % 1
        rgb = hsv_to_rgb(hue, saturation, 1.0, 1.0)
        background = brushes.color(*rgb)

    if s:
        saturation += s
        saturation = clamp(saturation, 0.0, 1.0)
        rgb = hsv_to_rgb(hue, saturation, 1.0, 1.0)
        background = brushes.color(*rgb)


def update():
    global flip, flip_start, rear_view, background_hue, background

    # unpack the x and y for the card
    x, y = card_pos

    width = 1

    # clear the screen
    screen.brush = background
    screen.clear()

    # ripple effect
    draw_background()

    if io.BUTTON_B in io.pressed:
        flip = True
        flip_start = io.ticks
        rear_view = not rear_view

    if io.BUTTON_UP in io.held:
        change_background(h=0.01)

    if io.BUTTON_DOWN in io.held:
        change_background(h=-0.01)

    if io.BUTTON_C in io.held:
        change_background(s=0.1)

    if io.BUTTON_A in io.held:
        change_background(s=-0.1)

    if flip:
        # create a spin animation that runs over 100ms
        speed = 90
        frame = io.ticks - flip_start

        # calculate the width of the tile during this part of the animation
        width = round(math.cos(frame / speed) * 3) / 3

        # ensure the width never reduces to zero or the icon disappears
        width = max(0.1, width) if width > 0 else min(-0.1, width)

        # once the animation has completed unset the spin flag
        if frame > (speed * 3):
            flip = False

    # draw the card
    id_body.transform = Matrix().translate(CX, y).scale(width, 1)
    id_outline.transform = Matrix().translate(CX, y).scale(width, 1)
    id_body.transform = id_body.transform.translate(-70, 0)
    id_outline.transform = id_outline.transform.translate(-70, 0)

    screen.brush = brushes.color(50, 50, 50, 100)
    id_body.transform = id_body.transform.translate(4, 4)
    screen.draw(id_body)

    screen.brush = brushes.color(255, 255, 255, 90)
    id_body.transform = id_body.transform.translate(-4, -4)
    screen.draw(id_body)
    screen.brush = brushes.color(0, 0, 0, 100)
    screen.draw(id_outline)

    photo_y = y + 15 + id_photo.height
    socials_y = 22

    if not flip:
        # Draw the card information
        screen.brush = brushes.color(0, 0, 0)
        if not rear_view:
            screen.font = large_font
            screen.blit(id_photo, CX - id_photo.width / 2, y + 10)
            center_text(id_name, photo_y)
            screen.font = small_font
            center_text(id_role, photo_y + 12)
        else:
            screen.font = large_font
            for account in id_socials.items():
                screen.brush = brushes.color(100, 100, 100)
                screen.draw(shapes.rounded_rectangle(20, socials_y, 17, 17, 3))
                screen.blit(account[1]["icon"], 20, socials_y)
                shadow_text(account[1]["handle"], 40, socials_y)
                socials_y += 21


def on_exit():
    pass


if __name__ == "__main__":
    run(update)
