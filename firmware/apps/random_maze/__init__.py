"""
A single player game demo. Navigate a set of mazes from the start (red) to the goal (green).
Mazes get bigger / harder with each increase in level.

Controls:
* U = Move Forward
* D = Move Backward
* C = Move Right
* A = Move left
* B = Continue (once the current level is complete)
"""

import os
import sys

sys.path.insert(0, "/system/apps/random_maze")
os.chdir("/system/apps/random_maze")

import gc
import random
import time
from collections import namedtuple

from badgeware import HEIGHT, WIDTH, io, run

# Setup for the display
font = PixelFont.load("/system/assets/fonts/nope.ppf")
screen.font = font
screen.antialias = Image.X4

# Colour Constants
WHITE = brushes.color(255, 255, 255)
BLACK = brushes.color(0, 0, 0)
RED = brushes.color(255, 0, 0)
GREEN = brushes.color(0, 255, 0)
PLAYER = brushes.color(227, 231, 110)
WALL = brushes.color(127, 125, 244)
BACKGROUND = brushes.color(60, 57, 169)
PATH = brushes.color((227 + 60) // 2, (231 + 57) // 2, (110 + 169) // 2)

CX, CY = WIDTH / 2, HEIGHT / 2

# Gameplay Constants
Position = namedtuple("Position", ("x", "y"))
MIN_MAZE_WIDTH = 2
MAX_MAZE_WIDTH = 5
MIN_MAZE_HEIGHT = 2
MAX_MAZE_HEIGHT = 5
WALL_SHADOW = 2
WALL_GAP = 1
TEXT_SHADOW = 2
MOVEMENT_SLEEP = 0.05
DIFFICULT_SCALE = 0.5

# Variables
complete = False                                # Has the game been completed?
level = 0                                       # The current "level" the player is on (affects difficulty)

player = None
builder = None

# Store text strings and calculate centre location
text_1_string = "Maze Complete!"
text_1_size = screen.measure_text(text_1_string)[0]

text_2_string = "Press B to continue"
text_2_size = screen.measure_text(text_2_string)[0]

text_1_location = ((WIDTH // 2) - (text_1_size // 2), CY - 15)
text_2_location = ((WIDTH // 2) - (text_2_size // 2), CY + 5)


# Classes
class Cell:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.bottom = True
        self.right = True
        self.visited = False

    @staticmethod
    def remove_walls(current, next):
        dx, dy = current.x - next.x, current.y - next.y
        if dx == 1:
            next.right = False
        if dx == -1:
            current.right = False
        if dy == 1:
            next.bottom = False
        if dy == -1:
            current.bottom = False


class MazeBuilder:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.cell_grid = []
        self.maze = []

    def build(self, width, height):
        if width <= 0:
            raise ValueError("width out of range. Expected greater than 0")

        if height <= 0:
            raise ValueError("height out of range. Expected greater than 0")

        self.width = width
        self.height = height

        # Set the starting cell to the centre
        cx = (self.width - 1) // 2
        cy = (self.height - 1) // 2

        gc.collect()

        # Create a grid of cells for building a maze
        self.cell_grid = [[Cell(x, y) for y in range(self.height)] for x in range(self.width)]
        cell_stack = []

        # Retrieve the starting cell and mark it as visited
        current = self.cell_grid[cx][cy]
        current.visited = True

        # Loop until every cell has been visited
        while True:
            next = self.choose_neighbour(current)
            # Was a valid neighbour found?
            if next is not None:
                # Move to the next cell, removing walls in the process
                next.visited = True
                cell_stack.append(current)
                Cell.remove_walls(current, next)
                current = next

            # No valid neighbour. Backtrack to a previous cell
            elif len(cell_stack) > 0:
                current = cell_stack.pop()

            # No previous cells, so exit
            else:
                break

        gc.collect()

        # Use the cell grid to create a maze grid of 0's and 1s
        self.maze = []

        row = [1]
        for _x in range(self.width):
            row.append(1)
            row.append(1)
        self.maze.append(row)

        for y in range(self.height):
            row = [1]
            for x in range(self.width):
                row.append(0)
                row.append(1 if self.cell_grid[x][y].right else 0)
            self.maze.append(row)

            row = [1]
            for x in range(self.width):
                row.append(1 if self.cell_grid[x][y].bottom else 0)
                row.append(1)
            self.maze.append(row)

        self.cell_grid.clear()
        gc.collect()

        self.grid_columns = (self.width * 2 + 1)
        self.grid_rows = (self.height * 2 + 1)

    def choose_neighbour(self, current):
        unvisited = []
        for dx in range(-1, 2, 2):
            x = current.x + dx
            if x >= 0 and x < self.width and not self.cell_grid[x][current.y].visited:
                unvisited.append((x, current.y))

        for dy in range(-1, 2, 2):
            y = current.y + dy
            if y >= 0 and y < self.height and not self.cell_grid[current.x][y].visited:
                unvisited.append((current.x, y))

        if len(unvisited) > 0:
            x, y = random.choice(unvisited)
            return self.cell_grid[x][y]

        return None

    def maze_width(self):
        return (self.width * 2) + 1

    def maze_height(self):
        return (self.height * 2) + 1

    def draw(self, display):
        # Draw the maze we have built. Each '1' in the array represents a wall
        for row in range(self.grid_rows):
            for col in range(self.grid_columns):
                # Calculate the screen coordinates
                x = (col * wall_separation) + offset_x
                y = (row * wall_separation) + offset_y

                if self.maze[row][col] == 1:
                    # Draw a wall shadow
                    screen.brush = BLACK
                    screen.draw(shapes.rectangle(x + WALL_SHADOW, y + WALL_SHADOW, wall_size, wall_size))

                    # Draw a wall top
                    screen.brush = WALL
                    screen.draw(shapes.rectangle(x, y, wall_size, wall_size))

                if self.maze[row][col] == 2:
                    # Draw the player path
                    screen.brush = PATH
                    screen.draw(shapes.rectangle(x, y, wall_size, wall_size))


class Player(object):
    def __init__(self, x, y, colour):
        self.x = x
        self.y = y
        self.colour = colour

    def position(self, x, y):
        self.x = x
        self.y = y

    def update(self, maze):

        if io.BUTTON_A in io.held and maze[self.y][self.x - 1] != 1:
            self.x -= 1
            time.sleep(MOVEMENT_SLEEP)

        elif io.BUTTON_C in io.held and maze[self.y][self.x + 1] != 1:
            self.x += 1
            time.sleep(MOVEMENT_SLEEP)

        elif io.BUTTON_UP in io.held and maze[self.y - 1][self.x] != 1:
            self.y -= 1
            time.sleep(MOVEMENT_SLEEP)

        elif io.BUTTON_DOWN in io.held and maze[self.y + 1][self.x] != 1:
            self.y += 1
            time.sleep(MOVEMENT_SLEEP)

        maze[self.y][self.x] = 2

    def draw(self, display):
        screen.brush = self.colour
        screen.draw(shapes.rectangle(self.x * wall_separation + offset_x,
                                     self.y * wall_separation + offset_y,
                                     wall_size, wall_size))


def build_maze():
    global wall_separation
    global wall_size
    global offset_x
    global offset_y
    global start
    global goal

    difficulty = int(level * DIFFICULT_SCALE)
    width = random.randrange(MIN_MAZE_WIDTH, MAX_MAZE_WIDTH)
    height = random.randrange(MIN_MAZE_HEIGHT, MAX_MAZE_HEIGHT)
    builder.build(width + difficulty, height + difficulty)

    wall_separation = min(HEIGHT // builder.grid_rows,
                          WIDTH // builder.grid_columns)
    wall_size = wall_separation - WALL_GAP

    offset_x = (WIDTH - (builder.grid_columns * wall_separation) + WALL_GAP) // 2
    offset_y = (HEIGHT - (builder.grid_rows * wall_separation) + WALL_GAP) // 2

    start = Position(1, builder.grid_rows - 2)
    goal = Position(builder.grid_columns - 2, 1)


def draw_maze():
    # Clear the screen to the background colour
    screen.brush = BACKGROUND
    screen.clear()

    # Draw the maze walls
    builder.draw(screen)

    # Draw the start location square
    screen.brush = RED
    screen.draw(shapes.rectangle(start.x * wall_separation + offset_x,
                                 start.y * wall_separation + offset_y,
                                 wall_size, wall_size))

    # Draw the goal location square
    screen.brush = GREEN
    screen.draw(shapes.rectangle(goal.x * wall_separation + offset_x,
                                 goal.y * wall_separation + offset_y,
                                 wall_size, wall_size))

    # Draw the player
    player.draw(screen)


def init():
    global builder, player
    # Create the maze builder and build the first maze and put
    builder = MazeBuilder()
    build_maze()

    # Create the player object
    player = Player(*start, PLAYER)

    draw_maze()


def update():
    global complete, builder, player, level

    draw_maze()

    if not complete:
        # Update the player's position in the maze
        player.update(builder.maze)

        # Check if any player has reached the goal position
        if player.x == goal.x and player.y == goal.y:
            complete = True

    if complete:
        # Draw banner
        screen.brush = PLAYER
        screen.draw(shapes.rounded_rectangle(10, CY - 24, WIDTH - 20, 50, 5))

        screen.brush = BLACK
        screen.draw(shapes.rounded_rectangle(10, CY - 24, WIDTH - 20, 50, 5).stroke(2))

        # Draw text
        screen.brush = BLACK
        screen.text(f"{text_1_string}", text_1_location[0], text_1_location[1])
        screen.text(f"{text_2_string}", text_2_location[0], text_2_location[1])

        if io.BUTTON_B in io.pressed:
            complete = False
            level += 1
            build_maze()
            player.position(*start)


def on_exit():
    pass


if __name__ == "__main__":
    run(update, init=init, on_exit=on_exit)
