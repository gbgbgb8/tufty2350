from picovector import algorithm
import math

size = 20

class Player:
  def __init__(self):
    self.pos = vec2(8, 8)
    self.angle = 0
    self.fov = 110

  def set_angle(self, angle):
    self.angle = angle

  def vector(self, offset=0, length=1):
    return vec2(
      math.cos((self.angle + offset) * (math.pi / 180)) * length,
      math.sin((self.angle + offset) * (math.pi / 180)) * length
    )

map = [
  [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
  [1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
  [1, 0, 0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
  [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
  [1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
  [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1],
  [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
  [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
  [1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
  [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
  [1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1],
  [1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1],
  [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1],
  [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1],
  [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
  [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]

def gtos(p):
  return vec2(
    160 + math.floor((p.x - player.pos.x) * size),
    120 + math.floor((p.y - player.pos.y) * size),
  )

def point_add(p1, p2):
  return vec2(
    p1.x + p2.x,
    p1.y + p2.y
  )

def map_value(x, y):
  x = int(x)
  y = int(y)
  if 0 <= x < len(map[0]) and 0 <= y < len(map):
    return map[y][x]
  return 1

def dda_cb(step, ip, ig, edge, offset, distance):
  mv = map_value(ig.x, ig.y)

  if mv == 1:
    sip = gtos(ip)

    b = 255 - (int(distance) * 10)
    pen(0, 0, 255, b)
    screen.line(gtos(player.pos), sip)


    sig = gtos(ig)
    pen(255, 255, 255)
    if edge == 0:
      screen.line(sig.x, sig.y, sig.x + size, sig.y)
    elif edge == 1:
      screen.line(sig.x + size, sig.y, sig.x + size, sig.y + size)
    elif edge == 2:
      screen.line(sig.x, sig.y + size, sig.x + size, sig.y + size)
    elif edge == 3:
      screen.line(sig.x, sig.y, sig.x, sig.y + size)



  return map_value(ig.x, ig.y) == 0

player = Player()

def update():
  global player
  screen.clear(color.rgb(20, 40, 60))

  player.pos = vec2(
    math.sin(io.ticks / 2000) * 3 + 8,
    math.cos(io.ticks / 2000) * 3 + 8
  )
  player.set_angle(io.ticks / 30)



  # cast rays for player sight
  for fova in range(-player.fov / 2, player.fov / 2):
    algorithm.dda(player.pos, player.vector(offset = fova), dda_cb)

  # draw player position
  pen(255, 255, 255)
  screen.circle(gtos(player.pos), 3)

  pen(255, 255, 255)
  screen.line(gtos(player.pos), gtos(player.pos + player.vector(length=100)))


  pen(100, 100, 100, 100)
  for x in range(0, len(map[0])):
    for y in range(0, len(map)):
      sp = gtos(vec2(x, y))
      if map_value(x, y) == 1:
        screen.rectangle(sp.x, sp.y, size, size)
