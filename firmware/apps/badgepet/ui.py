import math
from badgeware import screen, brushes, SpriteSheet, shapes, PixelFont, io, Image

# load user interface sprites
icons = SpriteSheet("assets/icons.png", 4, 1)
arrows = SpriteSheet("assets/arrows.png", 3, 1)
background_image = Image.load("/system/assets/squirrel-sprites/background.png")

# load in the font - font sheet generated from
screen.font = PixelFont.load("/system/assets/fonts/ark.ppf")

# brushes to match pets stats
stats_brushes = {
    "happy": brushes.color(141, 39, 135),
    "hunger": brushes.color(53, 141, 39),
    "clean": brushes.color(39, 106, 171),
    "warning": brushes.color(255, 0, 0, 200)
}

# icons to match pets stats
stats_icons = {
    "happy": icons.sprite(0, 0),
    "hunger": icons.sprite(1, 0),
    "clean": icons.sprite(2, 0)
}

# ui outline (contrast) colour
outline_brush = brushes.color(20, 30, 40, 150)
outline_brush_bold = brushes.color(20, 30, 40, 200)


# draw the background scenery
def background(pet):

    screen.blit(background_image, 0, 0)


# draw the title banner
def draw_header():
    screen.brush = outline_brush
    screen.draw(shapes.rounded_rectangle(40, -5, 160 - 80, 18, 3))

    screen.brush = brushes.color(255, 255, 255)
    center_text("Tufty", 0)

# draw a user action button with button name and label
def draw_button(x, y, label, active):
    width = 50

    # create an animated bounce effect
    bounce = math.sin(((io.ticks / 20) - x) / 10) * 2

    # draw the button label
    screen.brush = brushes.color(255, 255, 255, 255 if active else 150)
    shadow_text(label, y + (bounce / 2), x, x + width)

    # draw the button arrow
    arrows.sprite(2, 0).alpha = 255 if active else 150
    screen.blit(arrows.sprite(2, 0), x + (width / 2) - 4, y + bounce + 10)


# draw a statistics bar with icon and fill level
def draw_bar(name, x, y, amount):
    bar_width = 50

    screen.brush = outline_brush
    screen.draw(shapes.rounded_rectangle(x, y, bar_width, 12, 3))

    # draw the bar background
    screen.brush = outline_brush
    screen.draw(shapes.rounded_rectangle(x + 14, y + 3, bar_width - 17, 6, 2))

    # calculate how wide the bar "fill" is and clamp it to at least 3 pixels
    fill_width = round(max(((bar_width - 17) / 100) * amount, 3))

    # if bar level is low then alternate fill with red to show a warning
    screen.brush = stats_brushes[name]
    if amount <= 30:
        blink = round(io.ticks / 250) % 2 == 0
        if blink:
            screen.brush = stats_brushes["warning"]
    screen.draw(shapes.rounded_rectangle(x + 14, y + 3, fill_width, 6, 2))

    screen.brush = brushes.color(210, 230, 250, 50)
    screen.draw(shapes.rounded_rectangle(x + 15, y + 3, fill_width - 2, 1, 1))

    screen.blit(stats_icons[name], x, y)


def center_text(text, y, sx=0, ex=160):
    w, _ = screen.measure_text(text)
    screen.text(text, sx + ((ex - sx) / 2) - (w / 2), y)


def shadow_text(text, y, sx=0, ex=160):
    temp = screen.brush
    screen.brush = brushes.color(0, 0, 0, 100)
    center_text(text, y + 1, sx + 1, ex + 1)
    screen.brush = temp
    center_text(text, y, sx, ex)
