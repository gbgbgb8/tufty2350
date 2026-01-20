import math

skull = image.load("/system/assets/skull.png")
mona_sans = font.load("/system/assets/fonts/DynaPuff-Medium.af")
size = 24

def update():
  global size
  #screen.font = pixel_font.load("/system/assets/fonts/nope.ppf")
  screen.font = mona_sans

  screen.antialias = 2

  screen.clear(color.rgb(20, 40, 60))

  i = round(io.ticks / 200)
  i %= 10

  size = (math.sin(io.ticks / 1000) * 5) + 15
  message = f"""[pen:180,150,120]Upon the mast I gleam and grin, A sentinel of bone and sin. Wind and thunder, night and hull— None fear the sea like a [pen:230,220,200]pirate skull[pen:180,150,120].

Once I roared with breath and [pen:255,100,80]flame[pen:180,150,120], Now legend is my only name. But still I guard the [pen:255,200,80]plundered gold[pen:180,150,120], Grinning wide, forever bold.

[skull:]
"""

  pen(100, 255, 100, 150)

  x = 10
  y = 10
  width = math.sin(io.ticks / 500) * 40 + 110
  height = 200
  tokens = tokenise(screen, message)
  bounds = rect(x, y, width, height)
  measure(screen, tokens, bounds, line_spacing=1, word_spacing=1.05)
  import time

  pen(60, 80, 100, 100)
  screen.line(bounds.x, bounds.y, bounds.x + bounds.w, bounds.y)
  screen.line(bounds.x, bounds.y, bounds.x, bounds.y + bounds.h)
  screen.line(bounds.x, bounds.y + bounds.h, bounds.x + bounds.w, bounds.y + bounds.h)
  screen.line(bounds.x + bounds.w, bounds.y, bounds.x + bounds.w, bounds.y + bounds.h)




def pen_glyph_renderer(image, parameters, cursor, measure):
  if measure:
    return 0

  r = int(parameters[0])
  g = int(parameters[1])
  b = int(parameters[2])
  pen(r, g, b)

def skull_glyph_renderer(image, parameters, cursor, measure):
  if measure:
    return 24
  image.blit(skull, cursor)



def circle_glyph_renderer(image, parameters, cursor, measure):
  if measure:
    return 12

  image.shape(shape.circle(cursor.x + 6, cursor.y + 7, 6))

glyph_renderers = {
  "skull": skull_glyph_renderer,
  "pen": pen_glyph_renderer,
  "circle": circle_glyph_renderer
}


WORD = 1
SPACE = 2
LINE_BREAK = 3


def tokenise(image, text):
  tokens = []

  for line in text.splitlines():
    start, end = 0, 0
    i = 0
    while end < len(line):
      # check for a glyph_renderer
      if line.find("[", start) == start:
        end = line.find("]", start)
        # look ahead to see if this is an escape code
        glyph_renderer = line[start + 1:end]
        code, parameters = glyph_renderer.split(":")
        parameters = parameters.split(",")

        if code in glyph_renderers:
          w = glyph_renderers[code](None, parameters, None, True)
          tokens.append((glyph_renderers[code], w, tuple(parameters)))

        start = end + 1
        continue

      i += 1

      # search for the next space
      end = line.find(" ", start)
      if end == -1: end = len(line)

      glyph_renderer_start = line.find("[", start)
      if glyph_renderer_start != -1 and glyph_renderer_start < end:
        end = glyph_renderer_start

      # measure the text up to the space
      if end > start:
        width, _ = image.measure_text(line[start:end], size)
        tokens.append((WORD, width, line[start:end]))

      start = end
      if end < len(line) and line[end] == " ":
        tokens.append((SPACE,))
        start += 1


    tokens.append((LINE_BREAK,))

  return tokens

def measure(image, text, bounds, line_spacing=1, word_spacing=1):
  bounds.x = int(bounds.x)
  bounds.y = int(bounds.y)
  bounds.w = int(bounds.w)
  bounds.h = int(bounds.h)

  if isinstance(text, list):
    tokens = text
  else:
    tokens = tokenise(image, text)

  old_clip = image.clip
  image.clip = bounds

  c = vec2(bounds.x, bounds.y)
  b = rect()
  for token in tokens:
    if token[0] == WORD:
      if c.x + token[1] > bounds.x + bounds.w:
        c.x = bounds.x
        c.y += size * line_spacing
      image.text(token[2], c.x, c.y, size)
      c.x += token[1]
    elif token[0] == SPACE:
      c.x += (size / 3) * word_spacing
    elif token[0] == LINE_BREAK:
      c.x = bounds.x
      c.y += size * line_spacing
    else:
      if c.x + token[1] > bounds.x + bounds.w:
        c.x = bounds.x
        c.y += size * line_spacing

      token[0](image, token[2], c, False)
      c.x += token[1]

    b.w = max(b.w, c.x)
    b.h = max(b.h, c.y)

  image.clip = old_clip
  return b
