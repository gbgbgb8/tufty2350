import math

orange = color.rgb(246, 135, 4)
blue = color.rgb(28, 181, 202)
red = color.rgb(230, 60, 46)
green = color.rgb(9, 183, 117)
yellow = color.rgb(246, 167, 4)
purple = color.rgb(188, 96, 208)

# bright icon colours
bold = [orange, blue, red, green, yellow, purple]


# --orange: #f68704;
# --orange-rgb: 246, 135, 4;
# --pale: #bac0ca;
# --pale-rgb: 218, 216, 218;
# --pink: #f97eb5;
# --pink-rgb: 249, 126, 181;
# --purple: #bc60d0;
# --purple-rgb: 188, 96, 208;
# --red: #e63c2e;
# --red-rgb: 230, 60, 46;
# --theme-font: "Roboto", "Helvetica", "Tahoma", "Arial", sans-serif;
# --white: #ffffff;
# --white-rgb: 255, 255, 255;
# --yellow: #f6a704;
# --yellow-rgb: 246, 167, 4;

# create faded out variants for inactive icons
fade = 1.8
faded = [
    color.rgb(246, 135, 4, 120),
    color.rgb(28, 181, 202, 120),
    color.rgb(230, 60, 46, 120),
    color.rgb(9, 183, 117, 120),
    color.rgb(246, 167, 4, 120),
    color.rgb(188, 96, 208, 120),

    # color.rgb(211, 250, 55, 100),
    # color.rgb(48, 148, 255, 100),
    # color.rgb(95, 237, 131, 100),
    # color.rgb(225, 46, 251, 100),
    # color.rgb(216, 189, 14, 100),
    # color.rgb(255, 128, 210, 100),
    # color.rgb(211 / fade, 250 / fade, 55 / fade, 100),
    # color.rgb(48 / fade, 148 / fade, 255 / fade, 100),
    # color.rgb(95 / fade, 237 / fade, 131 / fade, 100),
    # color.rgb(225 / fade, 46 / fade, 251 / fade, 100),
    # color.rgb(216 / fade, 189 / fade, 14 / fade, 100),
    # color.rgb(255 / fade, 128 / fade, 210 / fade, 100),
]

# icon shape
squircle = shape.squircle(0, 0, 20, 4)
shade_brush = color.rgb(0, 0, 0, 50)


class Icon:
    active_icon = None

    def __init__(self, pos, name, index, icon):
        self.active = False
        self.pos = pos
        self.icon = icon
        self.name = name
        self.index = index
        self.spin = False

    def activate(self, active):
        # if this icon wasn't already activated then flag it for the spin animation
        if not self.active and active:
            self.spin = True
            self.spin_start = io.ticks
        self.active = active
        if active:
            Icon.active_icon = self

    def draw(self):
        width = 1
        sprite_width = self.icon.width
        sprite_offset = sprite_width / 2

        if self.spin:
            # create a spin animation that runs over 100ms
            speed = 100
            frame = io.ticks - self.spin_start

            # calculate the width of the tile during this part of the animation
            width = round(math.cos(frame / speed) * 3) / 3

            # ensure the width never reduces to zero or the icon disappears
            width = max(0.1, width) if width > 0 else min(-0.1, width)

            # determine how to offset and scale the sprite to match the tile width
            sprite_width = width * self.icon.width
            sprite_offset = abs(sprite_width) / 2

            # once the animation has completed unset the spin flag
            if frame > (speed * 6):
                self.spin = False

        # transform to the icon position
        squircle.transform = mat3().translate(*self.pos).scale(width, 1)

        # draw the icon shading
        screen.pen = shade_brush
        squircle.transform = squircle.transform.scale(1, 1)
        screen.shape(squircle)

        # draw the icon body
        squircle.transform = squircle.transform.scale(1, 1)
        if self.active:
            screen.pen = bold[self.index]
        else:
            screen.pen = faded[self.index]
        squircle.transform = squircle.transform.translate(-1, -1)
        screen.shape(squircle)
        squircle.transform = squircle.transform.translate(2, 2)
        screen.pen = shade_brush
        screen.shape(squircle)

        # draw the icon sprite
        if sprite_width > 0:
            self.icon.alpha = 255 if self.active else 100
            screen.blit(
                self.icon,
                rect(
                    self.pos[0] - sprite_offset - 1,
                    self.pos[1] - 13,
                    sprite_width,
                    24
                )
            )
