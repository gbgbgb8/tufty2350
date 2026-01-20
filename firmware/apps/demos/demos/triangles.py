import math, random

def update():
  screen.clear(color.rgb(20, 40, 60))

  random.seed(0)
  for i in range(100):
    x = math.sin(i + io.ticks / 100) * 40
    y = math.cos(i + io.ticks / 100) * 40

    p = vec2(x + bw.rnd(160), y + bw.rnd(120))
    p1 = vec2(p.x + bw.rnd(-30, 30), p.y + bw.rnd(-30, 30))
    p2 = vec2(p.x + bw.rnd(-30, 30), p.y + bw.rnd(-30, 30))
    p3 = vec2(p.x + bw.rnd(-30, 30), p.y + bw.rnd(-30, 30))

    r = bw.rnd(5, 20)
    pen(bw.rnd(255), bw.rnd(255), bw.rnd(255))
    screen.triangle(p1, p2, p3)

