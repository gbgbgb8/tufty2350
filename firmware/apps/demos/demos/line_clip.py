import math

def update():
  screen.clear(color.rgb(20, 40, 60))

  for i in range(100):

    pen(color.oklch(128, 128, (io.ticks / 100) + i + 150, 100))

    # line clipping to rect
    p1 = vec2(
      int(math.sin(i + io.ticks / 500) * 100 + 0),
      int(math.sin(i + io.ticks / 400) * 100 + 0)
    )

    p2 = vec2(
      int(math.sin(i + io.ticks / 300) * 100 + 320),
      int(math.sin(i + io.ticks / 200) * 100 + 240)
    )
    clip = rect(10, 10, 140, 100)
    algorithm.clip_line(p1, p2, clip)
    screen.line(p1, p2)

  pen(60, 80, 100, 100)
  screen.line(clip.x, clip.y, clip.x + clip.w, clip.y)
  screen.line(clip.x, clip.y, clip.x, clip.y + clip.h)
  screen.line(clip.x, clip.y + clip.h, clip.x + clip.w, clip.y + clip.h)
  screen.line(clip.x + clip.w, clip.y, clip.x + clip.w, clip.y + clip.h)

