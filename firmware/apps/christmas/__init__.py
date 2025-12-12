
# Your apps directory
APP_DIR = "/system/apps/christmas"

import os
import sys

# Standalone bootstrap for finding app assets
os.chdir(APP_DIR)

# Standalone bootstrap for module imports
sys.path.insert(0, APP_DIR)

import json
from random import randint
from urllib.urequest import urlopen
import math

import network
from badgeware import SpriteSheet, run

icons = SpriteSheet("ornament01.png", 1, 1)
ornament = icons.sprite(0, 0)

font_ziplock = pixel_font.load("/system/assets/fonts/ziplock.ppf")
font_awesome = pixel_font.load("/system/assets/fonts/awesome.ppf")
font_yolk = pixel_font.load("/system/assets/fonts/yolk.ppf")

screen.antialias = image.X2

RED = (169, 41, 33)
STAR_YELLOW = (250, 225, 0)

WIFI_TIMEOUT = 30

COUNTDOWN_API = "https://christmascountdown.live/api/timeleft"

WIFI_PASSWORD = None
WIFI_SSID = None

wlan = None
connected = False
ticks_start = None

task = None
days_remaining = None


def get_connection_details():
    global WIFI_PASSWORD, WIFI_SSID

    if WIFI_SSID is not None:
        if len(WIFI_SSID) > 0:
            return True

    try:
        sys.path.insert(0, "/")
        from secrets import WIFI_PASSWORD, WIFI_SSID
        sys.path.pop(0)
    except ImportError:
        WIFI_PASSWORD = None
        WIFI_SSID = None

    if len(WIFI_SSID) == 0:
        return False

    return True


def wlan_start():
    global wlan, ticks_start, connected, WIFI_PASSWORD, WIFI_SSID

    if ticks_start is None:
        ticks_start = io.ticks

    if connected:
        return True

    if wlan is None:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)

        if wlan.isconnected():
            return True

        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        print("Connecting to WiFi...")

    connected = wlan.isconnected()

    if io.ticks - ticks_start < WIFI_TIMEOUT * 1000:
        if connected:
            return True
    elif not connected:
        return False

    return True


def async_fetch_to_disk(url, file, force_update=False):
    try:
        # Grab the data
        response = urlopen(url)
        data = bytearray(512)
        total = 0
        with open(file, "wb") as f:
            while True:
                if (length := response.readinto(data)) == 0:
                    break
                total += length
                print(f"Fetched {total} bytes")
                f.write(data[:length])
                yield
        del data
        del response
    except Exception as e:
        raise RuntimeError(f"Fetch from {url} to {file} failed. {e}") from e


def get_days_remaining():
    global days_remaining

    if not days_remaining and connected:
        try:

            yield from async_fetch_to_disk(COUNTDOWN_API, "/christmas.json")
            r = json.loads(open("/christmas.json", "r").read())
            days_remaining = int(r["sleeps"])
            del r

        except OSError:
            return False


def fake_number():
    return randint(0, 99)


def centre_text(text, y):
    x = (screen.width / 2) - (screen.measure_text(text)[0] / 2)
    screen.text(text, x, y)


def wrap_text(text, x, y):
    lines = text.splitlines()
    for line in lines:
        _, h = screen.measure_text(line)
        screen.text(line, x, y)
        y += h * 0.8


class Snowflake:
    flakes = []

    def __init__(self):

        self.x = randint(0, screen.width)
        self.y = -20
        self.d = randint(5, 7)
        self.gravity = 0
        self.velocity = randint(1, 3)
        self.last_update = None

        Snowflake.flakes.append(self)

    def _update(self):
        alpha = max(75 - (self.y / 2), 0)
        screen.pen = color.rgb(255, 255, 255, alpha)
        screen.shape(shape.star(self.x, self.y, 5, self.d, self.d - 4))

        if self.last_update:
            time_delta = (io.ticks - self.last_update) / 1000
            self.velocity = self.velocity + (self.gravity * time_delta)
            self.y = self.y + self.velocity

        self.last_update = io.ticks

    @staticmethod
    def update():
        for f in Snowflake.flakes:
            f._update()


def connection_failed():

    screen.font = font_awesome
    screen.pen = color.rgb(255, 255, 255, 150)
    centre_text("Connection Failed!", 5)

    screen.text("1:", 10, 63)
    screen.text("2:", 10, 95)

    screen.font = font_yolk
    wrap_text("""Could not connect\nto the WiFi network.\n\n:-(""", 16, 20)
    wrap_text("""Edit 'secrets.py' to\nset WiFi details""", 30, 65)
    wrap_text("""Reload to see the\nfestive countdown!""", 30, 96)


def details_missing():

    screen.font = font_awesome
    screen.pen = color.rgb(255, 255, 255, 150)
    centre_text("Missing Details!", 5)

    screen.text("1:", 10, 23)
    screen.text("2:", 10, 60)
    screen.text("3:", 10, 87)

    screen.font = font_yolk
    wrap_text("""Put your badge into\ndisk mode (tap\nRESET twice)""", 30, 24)
    wrap_text("""Edit 'secrets.py' to\nset WiFi details""", 30, 61)
    wrap_text("""Reload to see the\nfestive countdown!""", 30, 88)


# Called once to initialise your app.
def init():
    pass


# Called every frame, update and render as you see fit!
def update():
    global days_remaining, task, connected

    screen.pen = brush.pattern(color.rgb(*RED), color.rgb(200, 50, 50), 31)
    screen.clear()

    if len(Snowflake.flakes) < 45:
        Snowflake()

    Snowflake.flakes = [flake for flake in Snowflake.flakes if flake.y < screen.height - 10]
    Snowflake.update()

    if get_connection_details():
        if wlan_start():

            if io.BUTTON_A in io.held and io.BUTTON_C in io.held:
                days_remaining = None
                connected = None

            if not days_remaining:
                if not task:
                    task = get_days_remaining()
                try:
                    next(task)
                except StopIteration:
                    task = None

            # box shadow
            screen.pen = color.rgb(0, 0, 0, 70)
            screen.shape(shape.rounded_rectangle(15 + 4, 25 + 4, screen.width - 30, screen.height - 50, 5))

            # main box
            screen.pen = color.rgb(255, 255, 255, 150)
            screen.shape(shape.rounded_rectangle(15, 25, screen.width - 30, screen.height - 50, 5))

            # box outline
            screen.pen = color.rgb(255, 255, 255, 175)
            screen.shape(shape.rounded_rectangle(15, 25, screen.width - 30, screen.height - 50, 5).stroke(2))

            screen.blit(ornament, rect(5, screen.height - 40, 32, 32))

            screen.pen = color.rgb(*STAR_YELLOW)
            star = shape.star(0, 0, 5, 9, 16)
            star_rotate = math.sin(io.ticks / 1000) * 100
            star.transform = mat3().translate(screen.width - 20, 25).rotate(star_rotate)
            screen.shape(star)
            screen.pen = color.rgb(0, 0, 0, 100)
            screen.shape(star.stroke(2))

            screen.font = font_ziplock
            screen.pen = color.rgb(10, 117, 51)
            centre_text(f"{days_remaining if days_remaining else fake_number()}", 40)

            screen.font = font_yolk
            centre_text("Sleeps Until Christmas!", 65)

        else:  # Connection Failed
            connection_failed()
    else:      # Get Details Failed
        details_missing()


# Handle saving your app state here
def on_exit():
    pass


# Standalone support for Thonny debugging
if __name__ == "__main__":
    run(update, init=init, on_exit=on_exit)
