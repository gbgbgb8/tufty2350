import sys
import os
from badgeware import run
import machine
import gc
# import powman

SKIP_CINEMATIC = True   # powman.get_wake_reason() == powman.WAKE_WATCHDOG

running_app = None


def quit_to_launcher(pin):
    global running_app
    getattr(running_app, "on_exit", lambda: None)()
    # If we reset while boot is low, bad times
    while not pin.value():
        pass
    machine.reset()


if not SKIP_CINEMATIC:
    startup = __import__("/system/apps/startup")

    run(startup.update)

    if sys.path[0].startswith("/system/apps"):
        sys.path.pop(0)

    del startup

    gc.collect()

standard_modules = [k for k in sys.modules.keys()]

menu = __import__("/system/apps/menu")

app = run(menu.update)

if sys.path[0].startswith("/system/apps"):
    sys.path.pop(0)

del menu

# make any module names imported by menu are freed for apps
for key, module in sys.modules.items():
    if key not in standard_modules:
        del sys.modules[key]

gc.collect()

# Stopping in Thonny can cause run(menu.update) to return None
if app is not None:
    # Don't pass the b press into the app
    while io.held:
        io.poll()

    machine.Pin.board.BUTTON_HOME.irq(
        trigger=machine.Pin.IRQ_FALLING, handler=quit_to_launcher
    )

    sys.path.insert(0, app)
    os.chdir(app)

    running_app = __import__(app)

    getattr(running_app, "init", lambda: None)()

    run(running_app.update)

    # Unreachable, in theory!
    machine.reset()

