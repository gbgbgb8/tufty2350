# A little library of methods to display text on the screen in mildly fancy ways.

black = color.rgb(0, 0, 0)
white = color.rgb(235, 245, 255)
small_font = pixel_font.load("/system/assets/fonts/ark.ppf")
large_font = pixel_font.load("/system/assets/fonts/absolute.ppf")


def center_text(text, y):
    # Centre text on screen

    w, h = screen.measure_text(text)
    screen.text(text, (screen.width / 2) - (w / 2), y)


def wrap_text(text, x, y):
    # Wrap text across multiple lines

    lines = text.splitlines()
    for line in lines:
        _, h = screen.measure_text(line)
        screen.text(line, x, y)
        y += h * 0.8


def stretch_text(text, x, y, distance, current_brush):
    # Stretch text across a given distance

    screen.pen = current_brush
    text_dims = screen.measure_text(text)
    width = text_dims[0]
    height = text_dims[1]

    # Calculate how much space should go between each letter
    totalspace = distance - width
    spacing = totalspace / (len(text) - 1)

    # Draw each character leaving that space between each one
    for i in text:
        screen.text(i, x, y)
        x += screen.measure_text(i)[0] + spacing
    return height


def user_message(caption, line1, line2=None, line3=None, line4=None, line5=None, line6=None):
    # A simple message screen with a heading and up to six lines of text.

    screen.pen = black
    screen.clear()
    screen.font = large_font
    screen.pen = white
    center_text(caption, 5)

    screen.font = small_font
    center_text(line1, 20)

    if line2:
        center_text(line2, 28)
    if line3:
        center_text(line3, 36)
    if line4:
        center_text(line4, 44)
    if line5:
        center_text(line5, 52)
    if line6:
        center_text(line6, 60)


def bullet_list(caption, bullet1, bullet2=None, bullet3=None):
    # A simple message screen with three bullet points.

    screen.pen = black
    screen.clear()
    screen.font = large_font
    screen.pen = white
    center_text(caption, 5)

    screen.text("1:", 10, 23)
    if bullet2:
        screen.text("2:", 10, 55)
    if bullet3:
        screen.text("3:", 10, 87)

    screen.font = small_font
    wrap_text(bullet1, 30, 24)
    if bullet2:
        wrap_text(bullet2, 30, 56)
    if bullet3:
        wrap_text(bullet3, 30, 88)
