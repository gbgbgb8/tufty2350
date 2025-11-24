import sys
import os
import math

sys.path.insert(0, "/system/apps/hydrate")
os.chdir("/system/apps/hydrate")

from badgeware import run, State, WIDTH, HEIGHT, clamp

CX = WIDTH / 2
CY = HEIGHT / 2

state = {
    "current": 0,
    "goal": 2000
}


WHITE = brushes.color(255, 255, 255)
BLACK = brushes.color(0, 0, 0)
SHADOW = brushes.color(0, 0, 0, 125)
BLUE1 = brushes.color(116, 204, 244)
BLUE2 = brushes.color(28, 163, 236)
BLUE3 = brushes.color(15, 94, 156)
GREEN = brushes.color(0, 150, 0)

screen.antialias = Image.X4

large_font = PixelFont.load("/system/assets/fonts/smart.ppf")
screen.font = large_font

graph_max = math.degrees(math.pi * 2)


def goal_met():
    return state["current"] >= state["goal"]


def draw_graph(x, y, r, value):

    v = clamp(value, 0, state["goal"])

    # scale the current amount in ml to degrees for our graph
    v = graph_max - (v * (graph_max / state["goal"]))

    # rotate and position it so 0 is at the top
    pie = shapes.pie(0, 0, r, 0, v)
    pie.transform = Matrix().translate(x, y).rotate(180)

    # Draw the  remaining non moving elements of the graph
    screen.brush = SHADOW
    screen.draw(shapes.circle(x + 2, y + 4, r))

    screen.brush = BLUE2 if not goal_met() else GREEN
    screen.draw(shapes.circle(x, y, r))

    screen.brush = BLUE3
    screen.draw(pie)
    screen.brush = WHITE
    screen.draw(shapes.circle(x - 1, y, r - 10))
    screen.brush = WHITE
    screen.draw(shapes.circle(x, y, r - 1).stroke(2))

    # if the graph is big enough, put the text in the centre.
    if r > 30:
        screen.brush = BLUE3
        text = f"{state["current"]}ml"
        tw = screen.measure_text(text)[0]
        tx = x - tw / 2
        ty = y - 6
        screen.text(text, tx, ty)


MENU_OPEN_Y = CY
MENU_CLOSED_Y = HEIGHT - 15
menu_pos = [0, MENU_CLOSED_Y, WIDTH, HEIGHT - CY]
speed = 11.0
show_menu = False
menu_value = 0


def draw_menu():
    global menu_pos, show_menu, menu_value

    # unpack the menu position
    x, y, w, h = menu_pos

    # Slide the menu open/close
    if y >= MENU_OPEN_Y and show_menu:
        direction = -1
        y += speed * direction
    elif y <= MENU_CLOSED_Y and not show_menu:
        direction = 1
        y += speed * direction

    # clamp the position
    y = clamp(y, MENU_OPEN_Y, MENU_CLOSED_Y)

    # store the values in the list
    menu_pos = [x, y, w, h]

    # darken the background when the menu is showing
    if show_menu:
        screen.brush = SHADOW
        screen.clear()

    # draw the menu background
    screen.brush = WHITE
    screen.draw(shapes.rounded_rectangle(x, y, w, h, 3, 3, 0, 0))

    # Show the menu elements if the menu is showing including during transition
    screen.brush = BLACK
    if y != MENU_CLOSED_Y:
        t = f"{menu_value}ml"
        tx = CX - screen.measure_text(str(t))[0] / 2
        screen.text(t, tx, y + 42)
        screen.text("-", 27, y + 42)
        screen.text("+", 127, y + 42)
        screen.text("OK", WIDTH - 16, y + 18)

        # gold star for meeting your daily goal! :)
        sx, sy = CX, y + 23
        if goal_met():
            screen.brush = brushes.color(255, 255, 0)
            screen.draw(shapes.star(sx, sy, 5, 9, 13))
        screen.brush = SHADOW
        screen.draw(shapes.star(sx, sy, 5, 9, 13).stroke(2))

    else:
        screen.text("^", CX - 3, y + 2)


def draw_background():

    cy = CY - 8
    cx = CX

    y = 0
    for row in range(12):
        x = 0
        for col in range(16):
            dist = math.sqrt((x + 5 - cx) ** 2 + (y + 5 - cy) ** 2)
            pulse = (math.sin(-io.ticks / 400 + (dist / 6)) / 2) + 0.5
            pulse = 0.8 + (pulse / 2)
            screen.brush = brushes.color(255, 255, 255, 50 * pulse)
            screen.rectangle(x, y, 10, 10)
            x += 10
        y += 10


def init():
    global state
    State.load("hydrate", state)


def update():
    global state, show_menu, menu_value

    if io.BUTTON_B in io.pressed:
        show_menu = not show_menu

    if show_menu:
        # increase/decrease the value to add
        # short press is +/- 5ml and long is +/- 25ml
        if io.BUTTON_A in io.pressed:
            menu_value -= 5
        elif io.BUTTON_A in io.held:
            menu_value -= 25
        if io.BUTTON_C in io.pressed:
            menu_value += 5
        elif io.BUTTON_C in io.held:
            menu_value += 25

        if io.BUTTON_DOWN in io.pressed:
            state["current"] += menu_value
            menu_value = 0
            show_menu = not show_menu
            State.save("hydrate", state)

        if io.BUTTON_UP in io.held:
            state["current"] = 0
            State.save("hydrate", state)

        menu_value = clamp(menu_value, 0, state["goal"])

    screen.brush = BLUE3
    screen.clear()

    draw_background()
    draw_graph(CX, CY - 8, 45, state["current"])
    draw_menu()


def on_exit():
    pass


if __name__ == "__main__":
    run(update, init=init, on_exit=on_exit)
