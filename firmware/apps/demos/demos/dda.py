from picovector import algorithm
import math

grid = 10
def dda_cb(step, ip, ig, edge, offset, distance):
  ip.x = ip.x * grid + 80
  ip.y = ip.y * grid + 60

  op = vec2()
  if edge ==  0 or edge == 2:
    op.x = int(ip.x) + offset
    op.y = int(ip.y)
  else:
    op.x = int(ip.x)
    op.y = int(ip.y) + offset

  pen(0, 255, 0)
  screen.circle(ip, 2)

  ig.x = ig.x * grid + 80
  ig.y = ig.y * grid + 60
  pen(0, 255, 0, 100)
  screen.rectangle(ig.x, ig.y, grid, grid)


  pen(255, 255, 255, 100)
  if edge == 0:
    screen.line(ig.x, ig.y, ig.x + grid, ig.y)
  elif edge == 1:
    screen.line(ig.x + grid, ig.y, ig.x + grid, ig.y + grid)
  elif edge == 2:
    screen.line(ig.x, ig.y + grid, ig.x + grid, ig.y + grid)
  elif edge == 3:
    screen.line(ig.x, ig.y, ig.x, ig.y + grid)

  return step < 10

def update():
  screen.clear(color.rgb(20, 40, 60))



  p = vec2(
    math.sin(io.ticks / 3000) * 2,
    math.cos(io.ticks/ 4000) * 2
  )
  v = vec2(
    math.cos(io.ticks / 5000) * 100,
    math.sin(io.ticks/ 6000) * 100
  )





  pen(40, 60, 80)
  for y in range(0, 120 / grid):
    screen.line(0, y * grid, 319, y * grid)

  for x in range(0, 160 / grid):
    screen.line(x * grid, 0, x * grid, 239)

  algorithm.dda(p, v, dda_cb)

  p.x = (p.x * grid) + 80
  p.y = (p.y * grid) + 60
  v.x = (v.x * grid)
  v.y = (v.y * grid)

  t = vec2(
    p.x + v.x,
    p.y + v.y
  )
  pen(255, 0, 255, 150)
  screen.line(p, t)

  pen(255, 255, 255)
  screen.shape(shape.circle(p, 2))

  pen(0, 255, 0)
  screen.shape(shape.circle(t, 2))