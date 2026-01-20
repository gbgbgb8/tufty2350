import math

skull = image.load("/system/assets/skull.png")

def update():
  screen.clear(color.rgb(20, 40, 60))

  t = mat3().translate(-12, -12).rotate(io.ticks / 100).translate(80, 60).scale(math.sin(io.ticks / 1000) * 4)
  imgbrush = brush.image(skull, t)

  pen(imgbrush)
  screen.shape(shape.circle(80, 60, 50))
