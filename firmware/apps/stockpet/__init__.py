# StockPet — Tamagotchi Stock Ticker for Tufty 2350
# v0.2 — Visual Polish: arms, shadow, smooth lerp, eye blink, particles
#
# Uses same secrets.py as Stocks app:
#   secrets.STOCKS, secrets.FINNHUB_KEY, secrets.TIMEZONE

APP_DIR = "/system/apps/stockpet"

import sys
import os
import time
import wifi
import secrets
import json
import math

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from badgeware import run, get_battery_level, is_charging, set_case_led, get_case_led, display

try:
    from usermessage import user_message
except ImportError:
    def user_message(title, lines):
        pass

print("[stockpet] App starting (v0.2)...")


# =============================================================================
# Configuration
# =============================================================================

FRESH_MS = 120_000
STALE_MS = 300_000
MARKET_CLOSED_STALE_MS = 900_000
BACKGROUND_CHECK_MS = 120_000
MOOD_CHANGE_MS = 15_000

THRESH_UP_BIG = 2.0
THRESH_DOWN_BIG = -2.0

MARKET_OPEN_HOUR = 9.5
MARKET_CLOSE_HOUR = 16.0

try:
    LOCAL_TZ = secrets.TIMEZONE
except AttributeError:
    LOCAL_TZ = -8
EST_OFFSET = LOCAL_TZ - (-5)

LERP_SPEED = 0.003          # smooth width transition per ms
BLINK_MIN_MS = 2500          # min time between blinks
BLINK_MAX_MS = 6000          # max time between blinks
BLINK_DURATION_MS = 150      # how long eyes stay closed
STAR_COUNT = 12
CONFETTI_COUNT = 10

COLORS = {
    "bg":           (0, 0, 0),
    "text":         (255, 255, 255),
    "up":           (0, 255, 0),
    "down":         (255, 0, 0),
    "neutral":      (200, 200, 200),
    "dim":          (100, 100, 100),
    "after_hours":  (100, 100, 255),
    "error":        (255, 100, 100),
    "skin":         (255, 200, 120),
    "skin_dark":    (220, 160, 80),
    "eye_white":    (255, 255, 255),
    "eye_pupil":    (20, 20, 20),
    "mouth":        (180, 60, 60),
    "blush":        (255, 120, 120),
    "sleep_bg":     (10, 10, 30),
    "zzz":          (120, 120, 200),
    "sweat":        (100, 180, 255),
    "tear":         (80, 140, 255),
    "shadow":       (15, 15, 15),
    "shadow_sleep": (5, 5, 20),
    "arm":          (220, 170, 90),
}

CONFETTI_COLORS = [
    (255, 50, 50), (50, 255, 50), (50, 100, 255),
    (255, 255, 50), (255, 50, 255), (50, 255, 255),
    (255, 150, 30), (200, 100, 255),
]


# =============================================================================
# Load Configuration
# =============================================================================

try:
    STOCKS = secrets.STOCKS
except AttributeError:
    STOCKS = ["TSLA", "PLTR", "SPY", "QQQ"]
print(f"[stockpet] Tracking tickers: {STOCKS}")

try:
    FINNHUB_KEY = secrets.FINNHUB_KEY
except AttributeError:
    FINNHUB_KEY = None
    print("[stockpet] WARNING: No FINNHUB_KEY, using mock data")


# =============================================================================
# Load Moods
# =============================================================================

def load_moods():
    default = {
        "up_big": ["STONKS!"], "up": ["Vibin'"], "flat": ["meh."],
        "down": ["Pain."], "down_big": ["GUH."], "sleeping": ["zzz..."],
    }
    try:
        with open(APP_DIR + "/moods.json", "r") as f:
            moods = json.load(f)
        print(f"[stockpet] Loaded moods.json: {sum(len(v) for v in moods.values())} phrases")
        return moods
    except Exception as e:
        print(f"[stockpet] Could not load moods.json ({e}), using defaults")
        return default

MOODS = load_moods()


# =============================================================================
# Mock Data
# =============================================================================

MOCK_DATA = {
    "TSLA": {"price": 420.69, "change": 5.25, "change_percent": 1.26},
    "PLTR": {"price": 35.50, "change": 0.75, "change_percent": 2.15},
    "SPY":  {"price": 385.20, "change": -2.10, "change_percent": -0.54},
    "QQQ":  {"price": 315.75, "change": 3.45, "change_percent": 1.10},
}

def get_mock_data(ticker):
    base = MOCK_DATA.get(ticker, MOCK_DATA["TSLA"])
    return {
        "price": base["price"], "change": base["change"],
        "change_percent": base["change_percent"],
        "last_fetch_ms": time.ticks_ms(), "error": False,
    }


class AppMode:
    STARTUP = 0
    NORMAL = 1
    INFO = 2


# =============================================================================
# Formatting
# =============================================================================

def _fmt_decimal(val, decimals=2):
    rounded = round(val, decimals)
    s = str(rounded)
    if "." not in s:
        return s + "." + "0" * decimals
    integer, frac = s.split(".")
    while len(frac) < decimals:
        frac += "0"
    return integer + "." + frac

def fmt_price(val):
    return "$" + _fmt_decimal(val, 2)

def fmt_change(val):
    prefix = "+" if val >= 0 else ""
    return prefix + _fmt_decimal(val, 2)

def fmt_percent(val):
    return fmt_change(val) + "%"

def fmt_time_ago(ms_ago):
    if ms_ago < 0:
        return "Never"
    secs = ms_ago // 1000
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    return f"{secs // 3600}h ago"


# =============================================================================
# Market Status
# =============================================================================

_market_cache = {"is_open": None, "session": None, "holiday": None, "last_fetch": 0}
MARKET_CACHE_MS = 60_000

def is_market_open_fallback():
    try:
        now = time.localtime()
        weekday = now[6]
        hour = now[3]
        minute = now[4]
        est_hour = hour - EST_OFFSET
        est_weekday = weekday
        if est_hour >= 24:
            est_hour -= 24
            est_weekday = (weekday + 1) % 7
        elif est_hour < 0:
            est_hour += 24
            est_weekday = (weekday - 1) % 7
        if est_weekday > 4:
            return False, None, None
        current_time = est_hour + minute / 60.0
        is_open = MARKET_OPEN_HOUR <= current_time < MARKET_CLOSE_HOUR
        return is_open, "regular" if is_open else None, None
    except Exception:
        return True, None, None

def fetch_market_status():
    global _market_cache
    now = time.ticks_ms()
    if _market_cache["is_open"] is not None and time.ticks_diff(now, _market_cache["last_fetch"]) < MARKET_CACHE_MS:
        return _market_cache["is_open"], _market_cache["session"], _market_cache["holiday"]
    if FINNHUB_KEY is None:
        return is_market_open_fallback()
    try:
        import urequests
        url = f"https://finnhub.io/api/v1/stock/market-status?exchange=US&token={FINNHUB_KEY}"
        resp = urequests.get(url, timeout=5)
        if resp.status_code != 200:
            resp.close()
            return is_market_open_fallback()
        data = json.loads(resp.text)
        resp.close()
        is_open = data.get("isOpen", False)
        session = data.get("session")
        holiday = data.get("holiday")
        _market_cache.update({"is_open": is_open, "session": session, "holiday": holiday, "last_fetch": now})
        print(f"[stockpet] Market: open={is_open}, session={session}, holiday={holiday}")
        return is_open, session, holiday
    except Exception as e:
        print(f"[stockpet] Market status fetch failed: {e}")
        return is_market_open_fallback()


# =============================================================================
# Data Fetching
# =============================================================================

def fetch_stock_data(ticker):
    if FINNHUB_KEY is None:
        print(f"[stockpet] Mock data for {ticker}")
        return get_mock_data(ticker)
    try:
        import urequests
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}"
        print(f"[stockpet] Fetching {ticker}...")
        resp = urequests.get(url, timeout=10)
        if resp.status_code != 200:
            print(f"[stockpet] HTTP {resp.status_code} for {ticker}")
            resp.close()
            return None
        data = json.loads(resp.text)
        resp.close()
        if data.get("c", 0) == 0:
            print(f"[stockpet] No price data for {ticker}")
            return None
        result = {
            "price": data["c"],
            "change": data.get("d", 0) or 0,
            "change_percent": data.get("dp", 0) or 0,
            "last_fetch_ms": time.ticks_ms(),
            "error": False,
        }
        print(f"[stockpet] {ticker}: ${result['price']} ({fmt_percent(result['change_percent'])})")
        return result
    except Exception as e:
        print(f"[stockpet] Fetch error for {ticker}: {e}")
        return None

def get_data_age(stock_data):
    if stock_data is None:
        return 999999999
    return time.ticks_diff(time.ticks_ms(), stock_data.get("last_fetch_ms", 0))

def is_data_fresh(stock_data, market_open):
    return get_data_age(stock_data) < FRESH_MS

def is_data_stale(stock_data, market_open):
    threshold = STALE_MS if market_open else MARKET_CLOSED_STALE_MS
    return get_data_age(stock_data) > threshold


# =============================================================================
# Helpers
# =============================================================================

def rgb(r, g, b):
    return color.rgb(r, g, b)

def get_wifi_ssid():
    try:
        return getattr(secrets, "WIFI_SSID", "Connected") if wifi.is_connected() else "Not connected"
    except Exception:
        return "Unknown"

def get_ip_address():
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        return wlan.ifconfig()[0] if wlan.isconnected() else "N/A"
    except Exception:
        return "N/A"

def get_mood_key(change_percent, market_open):
    if not market_open:
        return "sleeping"
    if change_percent >= THRESH_UP_BIG:
        return "up_big"
    elif change_percent > 0.1:
        return "up"
    elif change_percent <= THRESH_DOWN_BIG:
        return "down_big"
    elif change_percent < -0.1:
        return "down"
    else:
        return "flat"

def pick_mood_text(mood_key, index):
    phrases = MOODS.get(mood_key, ["..."])
    return phrases[index % len(phrases)]

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def lerp(current, target, speed, dt):
    diff = target - current
    step = speed * dt
    if abs(diff) < step:
        return target
    return current + (step if diff > 0 else -step)


# =============================================================================
# Simple PRNG for particles (xorshift32)
# =============================================================================

_prng_state = 12345

def _seed_prng(s):
    global _prng_state
    _prng_state = s if s != 0 else 1

def _prng_next():
    global _prng_state
    x = _prng_state & 0xFFFFFFFF
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= (x >> 17)
    x ^= (x << 5) & 0xFFFFFFFF
    _prng_state = x & 0xFFFFFFFF
    return x

def prng_range(lo, hi):
    return lo + (_prng_next() % (hi - lo + 1))


# =============================================================================
# Background Particles
# =============================================================================

class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color_idx")

    def __init__(self, x, y, vx, vy, life, color_idx=0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.color_idx = color_idx


class ParticleSystem:
    def __init__(self):
        self.stars = []
        self.confetti = []
        self._last_spawn_ms = 0
        self._init_stars()
        print(f"[stockpet] Particles: {len(self.stars)} stars ready")

    def _init_stars(self):
        _seed_prng(42)
        self.stars = []
        for _ in range(STAR_COUNT):
            self.stars.append({
                "x": prng_range(4, 156),
                "y": prng_range(22, 85),
                "speed": prng_range(1, 3),
                "phase": prng_range(0, 1000),
                "bright": prng_range(40, 120),
            })

    def spawn_confetti(self, cx, current_ms):
        if len(self.confetti) >= CONFETTI_COUNT:
            return
        if current_ms - self._last_spawn_ms < 200:
            return
        self._last_spawn_ms = current_ms
        self.confetti.append(Particle(
            x=prng_range(cx - 30, cx + 30),
            y=prng_range(20, 35),
            vx=prng_range(-10, 10) / 10.0,
            vy=prng_range(5, 15) / 10.0,
            life=prng_range(800, 1800),
            color_idx=prng_range(0, len(CONFETTI_COLORS) - 1),
        ))

    def update_confetti(self, dt):
        alive = []
        for p in self.confetti:
            p.life -= dt
            if p.life <= 0:
                continue
            p.x += p.vx
            p.y += p.vy
            p.vy += 0.02 * dt
            if p.y < 120:
                alive.append(p)
        self.confetti = alive

    def draw_stars(self, current_ms, low_battery):
        for s in self.stars:
            twinkle = math.sin((current_ms + s["phase"]) * 0.001 * s["speed"])
            bright = int(s["bright"] * (0.5 + 0.5 * twinkle))
            if bright < 10:
                continue
            if low_battery:
                bright = int(bright * 0.85)
            screen.pen = rgb(bright, bright, int(bright * 1.2))
            screen.rectangle(s["x"], s["y"], 1, 1)

    def draw_confetti(self, low_battery):
        for p in self.confetti:
            fade = p.life / p.max_life
            col = CONFETTI_COLORS[p.color_idx]
            c = tuple(int(v * fade) for v in col)
            if low_battery:
                c = tuple(int(v * 0.85) for v in c)
            screen.pen = rgb(*c)
            if int(p.x) % 2 == 0:
                screen.rectangle(int(p.x), int(p.y), 2, 1)
            else:
                screen.rectangle(int(p.x), int(p.y), 1, 2)


# =============================================================================
# Pet Drawing
# =============================================================================

class PetRenderer:
    """Draws the pet using primitives. Sprite-replaceable later.
    v0.2: arms, shadow, smooth lerp, blink, particles.
    """

    BASE_BODY_W = 36
    BASE_BODY_H = 30
    MIN_SCALE = 0.45
    MAX_SCALE = 1.8
    PET_CENTER_X = 80
    PET_CENTER_Y = 62

    def __init__(self):
        self._current_scale = 1.0
        self._last_update_ms = time.ticks_ms()
        self._blink_active = False
        self._blink_start_ms = 0
        self._next_blink_ms = time.ticks_ms() + prng_range(BLINK_MIN_MS, BLINK_MAX_MS)
        self.particles = ParticleSystem()
        print("[stockpet] PetRenderer initialized (v0.2)")

    def _get_target_scale(self, change_percent, market_open):
        if not market_open:
            return 0.85
        pct = clamp(change_percent, -5.0, 5.0)
        if pct >= 0:
            return 1.0 + (pct / 5.0) * (self.MAX_SCALE - 1.0)
        else:
            return 1.0 + (pct / 5.0) * (1.0 - self.MIN_SCALE)

    def _update_smooth_scale(self, change_percent, market_open, current_ms):
        target = self._get_target_scale(change_percent, market_open)
        dt = min(time.ticks_diff(current_ms, self._last_update_ms), 100)
        self._last_update_ms = current_ms
        self._current_scale = lerp(self._current_scale, target, LERP_SPEED, dt)
        return self._current_scale

    def _update_blink(self, current_ms, mood_key):
        if mood_key == "sleeping":
            return False
        if self._blink_active:
            if time.ticks_diff(current_ms, self._blink_start_ms) >= BLINK_DURATION_MS:
                self._blink_active = False
                self._next_blink_ms = current_ms + prng_range(BLINK_MIN_MS, BLINK_MAX_MS)
                return False
            return True
        else:
            if time.ticks_diff(current_ms, self._next_blink_ms) >= 0:
                self._blink_active = True
                self._blink_start_ms = current_ms
                return True
            return False

    def _dim(self, rgb_tuple, low_battery):
        if low_battery:
            return tuple(int(c * 0.85) for c in rgb_tuple)
        return rgb_tuple

    def draw(self, change_percent, market_open, mood_key, current_ms, low_battery=False):
        scale = self._update_smooth_scale(change_percent, market_open, current_ms)
        is_blinking = self._update_blink(current_ms, mood_key)
        bw = int(self.BASE_BODY_W * scale)
        bh = self.BASE_BODY_H
        cx = self.PET_CENTER_X
        cy = self.PET_CENTER_Y

        bounce_y = 0
        tremble_x = 0
        breathe_w = 0

        if mood_key == "sleeping":
            breathe_w = int(2 * math.sin(current_ms * 0.002))
            cy += 4
        elif mood_key == "up_big":
            bounce_y = int(4 * abs(math.sin(current_ms * 0.006)))
            breathe_w = int(2 * math.sin(current_ms * 0.003))
        elif mood_key == "up":
            bounce_y = int(2 * abs(math.sin(current_ms * 0.004)))
            breathe_w = int(1 * math.sin(current_ms * 0.003))
        elif mood_key == "down":
            tremble_x = int(1 * math.sin(current_ms * 0.012))
            breathe_w = int(1 * math.sin(current_ms * 0.002))
        elif mood_key == "down_big":
            tremble_x = int(2 * math.sin(current_ms * 0.025))
            breathe_w = int(1 * math.sin(current_ms * 0.002))
        else:
            breathe_w = int(1 * math.sin(current_ms * 0.002))

        fw = bw + breathe_w
        fx = cx + tremble_x
        fy = cy - bounce_y

        # Background particles (behind pet)
        if mood_key == "sleeping":
            self.particles.draw_stars(current_ms, low_battery)
        elif mood_key == "up_big":
            self.particles.spawn_confetti(cx, current_ms)
            self.particles.update_confetti(16)
            self.particles.draw_confetti(low_battery)

        self._draw_shadow(fx, fy, fw, bh, bounce_y, mood_key, low_battery)
        self._draw_body(fx, fy, fw, bh, mood_key, low_battery)
        self._draw_arms(fx, fy, fw, bh, mood_key, current_ms, low_battery)
        self._draw_face(fx, fy, fw, bh, mood_key, current_ms, is_blinking, low_battery)
        self._draw_legs(fx, fy, fw, bh, mood_key, current_ms, low_battery)
        self._draw_effects(fx, fy, fw, bh, mood_key, current_ms, low_battery)

    def _draw_shadow(self, cx, cy, w, h, bounce_y, mood_key, low_battery):
        ground_y = 87
        shadow_col = COLORS["shadow_sleep"] if mood_key == "sleeping" else COLORS["shadow"]
        shadow_col = self._dim(shadow_col, low_battery)
        sw = max(8, int(w * 0.8) - bounce_y)
        sh = max(2, 4 - bounce_y // 2)
        sx = cx - sw // 2
        screen.pen = rgb(*shadow_col)
        screen.rectangle(sx + 2, ground_y, sw - 4, sh)
        if sh > 2:
            screen.rectangle(sx, ground_y + 1, sw, sh - 2)

    def _draw_body(self, cx, cy, w, h, mood_key, low_battery):
        skin = self._dim(COLORS["skin"], low_battery)
        x = cx - w // 2
        y = cy - h // 2
        inset = max(4, w // 6)
        cap_h = max(3, h // 5)
        screen.pen = rgb(*skin)
        screen.rectangle(x + inset, y, w - inset * 2, cap_h)
        screen.rectangle(x, y + cap_h, w, h - cap_h * 2)
        screen.rectangle(x + inset, y + h - cap_h, w - inset * 2, cap_h)
        side_inset = max(2, inset // 2)
        screen.rectangle(x + side_inset, y + cap_h // 2, w - side_inset * 2, cap_h // 2)
        screen.rectangle(x + side_inset, y + h - cap_h, w - side_inset * 2, cap_h // 2)
        if w > 16:
            bw2 = max(4, w // 3)
            bh2 = max(4, h // 3)
            screen.pen = rgb(*self._dim((255, 220, 160), low_battery))
            screen.rectangle(cx - bw2 // 2, cy - bh2 // 2 + 2, bw2, bh2)

    def _draw_arms(self, cx, cy, w, h, mood_key, current_ms, low_battery):
        """Arms: raised when happy, drooped when sad, tucked when sleeping."""
        arm_col = self._dim(COLORS["arm"], low_battery)
        screen.pen = rgb(*arm_col)
        arm_len = max(5, w // 5)
        arm_w = 3
        body_left = cx - w // 2
        body_right = cx + w // 2
        arm_y_base = cy - 2

        if mood_key == "sleeping":
            tuck_y = cy + h // 4
            screen.rectangle(body_left - 2, tuck_y, 4, arm_w)
            screen.rectangle(body_right - 2, tuck_y, 4, arm_w)
        elif mood_key == "up_big":
            wave = int(2 * math.sin(current_ms * 0.008))
            for i in range(arm_len):
                screen.rectangle(body_left - 1 - i, arm_y_base - i + wave, 1, arm_w)
            for i in range(arm_len):
                screen.rectangle(body_right + i, arm_y_base - i - wave, 1, arm_w)
        elif mood_key == "up":
            for i in range(arm_len):
                screen.rectangle(body_left - 1 - i, arm_y_base - i // 2, 1, arm_w)
            for i in range(arm_len):
                screen.rectangle(body_right + i, arm_y_base - i // 2, 1, arm_w)
        elif mood_key == "down":
            for i in range(arm_len):
                screen.rectangle(body_left - 1 - i, arm_y_base + i // 2, 1, arm_w)
            for i in range(arm_len):
                screen.rectangle(body_right + i, arm_y_base + i // 2, 1, arm_w)
        elif mood_key == "down_big":
            for i in range(arm_len):
                screen.rectangle(body_left - 2, arm_y_base + i, arm_w, 1)
            for i in range(arm_len):
                screen.rectangle(body_right - 1, arm_y_base + i, arm_w, 1)
        else:  # flat
            screen.rectangle(body_left - arm_len, arm_y_base, arm_len, arm_w)
            screen.rectangle(body_right, arm_y_base, arm_len, arm_w)

    def _draw_face(self, cx, cy, w, h, mood_key, current_ms, is_blinking, low_battery):
        face_y = cy - h // 4
        eye_spacing = max(6, w // 4)
        eye_y = face_y

        # Blink override: draw closed eyes + mood mouth
        if is_blinking and mood_key not in ("sleeping", "down_big"):
            line_w = max(3, w // 8)
            screen.pen = rgb(*self._dim(COLORS["eye_pupil"], low_battery))
            screen.rectangle(cx - eye_spacing - line_w // 2, eye_y, line_w, 1)
            screen.rectangle(cx + eye_spacing - line_w // 2, eye_y, line_w, 1)
            self._draw_mouth(cx, face_y, w, mood_key, low_battery)
            return

        if mood_key == "sleeping":
            line_w = max(3, w // 8)
            screen.pen = rgb(*self._dim(COLORS["eye_pupil"], low_battery))
            screen.rectangle(cx - eye_spacing - line_w // 2, eye_y, line_w, 1)
            screen.rectangle(cx + eye_spacing - line_w // 2, eye_y, line_w, 1)
            screen.pen = rgb(*self._dim(COLORS["mouth"], low_battery))
            screen.rectangle(cx - 2, face_y + 8, 4, 1)

        elif mood_key == "down_big":
            sz = max(2, w // 10)
            screen.pen = rgb(*self._dim(COLORS["eye_pupil"], low_battery))
            for side in [-1, 1]:
                ex = cx + side * eye_spacing
                screen.line(ex - sz, eye_y - sz, ex + sz, eye_y + sz)
                screen.line(ex - sz, eye_y + sz, ex + sz, eye_y - sz)
            self._draw_mouth(cx, face_y, w, mood_key, low_battery)

        elif mood_key == "down":
            eye_r = max(2, w // 10)
            screen.pen = rgb(*self._dim(COLORS["eye_white"], low_battery))
            screen.circle(cx - eye_spacing, eye_y, eye_r + 1)
            screen.circle(cx + eye_spacing, eye_y, eye_r + 1)
            screen.pen = rgb(*self._dim(COLORS["eye_pupil"], low_battery))
            screen.circle(cx - eye_spacing, eye_y + 1, eye_r)
            screen.circle(cx + eye_spacing, eye_y + 1, eye_r)
            self._draw_mouth(cx, face_y, w, mood_key, low_battery)

        elif mood_key == "up_big":
            eye_r = max(2, w // 8)
            screen.pen = rgb(*self._dim(COLORS["eye_white"], low_battery))
            screen.circle(cx - eye_spacing, eye_y, eye_r + 1)
            screen.circle(cx + eye_spacing, eye_y, eye_r + 1)
            screen.pen = rgb(*self._dim(COLORS["eye_pupil"], low_battery))
            screen.circle(cx - eye_spacing, eye_y, eye_r)
            screen.circle(cx + eye_spacing, eye_y, eye_r)
            screen.pen = rgb(*self._dim(COLORS["eye_white"], low_battery))
            screen.rectangle(cx - eye_spacing - 1, eye_y - 1, 1, 1)
            screen.rectangle(cx + eye_spacing - 1, eye_y - 1, 1, 1)
            self._draw_mouth(cx, face_y, w, mood_key, low_battery)
            screen.pen = rgb(*self._dim(COLORS["blush"], low_battery))
            blush_x = max(8, w // 3)
            screen.rectangle(cx - blush_x - 2, face_y + 5, 3, 2)
            screen.rectangle(cx + blush_x, face_y + 5, 3, 2)

        elif mood_key == "up":
            eye_r = max(2, w // 9)
            screen.pen = rgb(*self._dim(COLORS["eye_white"], low_battery))
            screen.circle(cx - eye_spacing, eye_y, eye_r + 1)
            screen.circle(cx + eye_spacing, eye_y, eye_r + 1)
            screen.pen = rgb(*self._dim(COLORS["eye_pupil"], low_battery))
            screen.circle(cx - eye_spacing, eye_y, eye_r)
            screen.circle(cx + eye_spacing, eye_y, eye_r)
            self._draw_mouth(cx, face_y, w, mood_key, low_battery)

        else:  # flat
            eye_r = max(1, w // 10)
            screen.pen = rgb(*self._dim(COLORS["eye_pupil"], low_battery))
            screen.circle(cx - eye_spacing, eye_y, eye_r)
            screen.circle(cx + eye_spacing, eye_y, eye_r)
            self._draw_mouth(cx, face_y, w, mood_key, low_battery)

    def _draw_mouth(self, cx, face_y, w, mood_key, low_battery):
        screen.pen = rgb(*self._dim(COLORS["mouth"], low_battery))
        if mood_key == "up_big":
            mw = max(6, w // 3)
            screen.line(cx - mw, face_y + 7, cx, face_y + 11)
            screen.line(cx, face_y + 11, cx + mw, face_y + 7)
        elif mood_key == "up":
            mw = max(4, w // 4)
            screen.line(cx - mw, face_y + 7, cx, face_y + 10)
            screen.line(cx, face_y + 10, cx + mw, face_y + 7)
        elif mood_key in ("down_big", "down"):
            mw = max(4, w // 4 if mood_key == "down_big" else w // 5)
            depth = 11 if mood_key == "down_big" else 10
            screen.line(cx - mw, face_y + 8, cx, face_y + depth)
            screen.line(cx, face_y + depth, cx + mw, face_y + 8)
        else:
            mw = max(3, w // 5)
            screen.rectangle(cx - mw // 2, face_y + 8, mw, 1)

    def _draw_legs(self, cx, cy, w, h, mood_key, current_ms, low_battery):
        leg_w = max(3, w // 6)
        leg_h = 6
        body_bottom = cy + h // 2
        screen.pen = rgb(*self._dim(COLORS["skin_dark"], low_battery))
        spread = max(4, w // 4)

        if mood_key == "sleeping":
            screen.rectangle(cx - spread - leg_w // 2, body_bottom - 1, leg_w, 3)
            screen.rectangle(cx + spread - leg_w // 2, body_bottom - 1, leg_w, 3)
        elif mood_key == "up_big":
            step = int(3 * math.sin(current_ms * 0.008))
            screen.rectangle(cx - spread - leg_w // 2, body_bottom, leg_w, leg_h + step)
            screen.rectangle(cx + spread - leg_w // 2, body_bottom, leg_w, leg_h - step)
        elif mood_key == "down_big":
            jitter = int(1 * math.sin(current_ms * 0.02))
            screen.rectangle(cx - spread - leg_w // 2 + jitter, body_bottom, leg_w, leg_h)
            screen.rectangle(cx + spread - leg_w // 2 - jitter, body_bottom, leg_w, leg_h)
        else:
            screen.rectangle(cx - spread - leg_w // 2, body_bottom, leg_w, leg_h)
            screen.rectangle(cx + spread - leg_w // 2, body_bottom, leg_w, leg_h)

        # Feet
        foot_w = leg_w + 2
        foot_h = 2
        if mood_key != "sleeping":
            foot_y = body_bottom + leg_h
            if mood_key == "up_big":
                step = int(3 * math.sin(current_ms * 0.008))
                screen.rectangle(cx - spread - foot_w // 2, foot_y + step, foot_w, foot_h)
                screen.rectangle(cx + spread - foot_w // 2, foot_y - step, foot_w, foot_h)
            else:
                screen.rectangle(cx - spread - foot_w // 2, foot_y, foot_w, foot_h)
                screen.rectangle(cx + spread - foot_w // 2, foot_y, foot_w, foot_h)

    def _draw_effects(self, cx, cy, w, h, mood_key, current_ms, low_battery):
        if mood_key == "sleeping":
            self._draw_zzz(cx + w // 2 + 6, cy - h // 2 - 8, current_ms, low_battery)
        elif mood_key == "down_big":
            face_y = cy - h // 4
            eye_spacing = max(6, w // 4)
            tear_phase = (current_ms % 1200) / 1200.0
            tear_y = int(face_y + 3 + tear_phase * 14)
            if (1.0 - tear_phase) > 0.3:
                screen.pen = rgb(*self._dim(COLORS["tear"], low_battery))
                screen.rectangle(cx - eye_spacing, tear_y, 1, 2)
                screen.rectangle(cx + eye_spacing, tear_y, 1, 2)
        elif mood_key == "down":
            sweat_phase = (current_ms % 2000) / 2000.0
            sweat_y = int(cy - h // 3 + sweat_phase * 10)
            if sweat_phase < 0.7:
                screen.pen = rgb(*self._dim(COLORS["sweat"], low_battery))
                screen.rectangle(cx + w // 2 + 3, sweat_y, 2, 2)
        elif mood_key == "up_big":
            phase1 = (current_ms % 2500) / 2500.0
            phase2 = ((current_ms + 1200) % 2500) / 2500.0
            screen.pen = rgb(*self._dim(COLORS["up"], low_battery))
            for phase, x_off in [(phase1, -w // 2 - 8), (phase2, w // 2 + 6)]:
                if phase < 0.8:
                    my = int(cy - phase * 30)
                    mx = cx + x_off
                    screen.rectangle(mx, my, 1, 5)
                    screen.rectangle(mx - 1, my + 1, 3, 1)
                    screen.rectangle(mx - 1, my + 3, 3, 1)

    def _draw_zzz(self, x, y, current_ms, low_battery):
        screen.pen = rgb(*self._dim(COLORS["zzz"], low_battery))
        for i in range(3):
            phase = ((current_ms + i * 800) % 2400) / 2400.0
            zx = x + i * 5
            zy = int(y - phase * 12)
            sz = 2 + i
            screen.rectangle(zx, zy, sz, 1)
            screen.line(zx + sz - 1, zy, zx, zy + sz)
            screen.rectangle(zx, zy + sz, sz, 1)


# =============================================================================
# Display
# =============================================================================

class PetDisplay:
    def __init__(self):
        self.font_small = pixel_font.load("/system/assets/fonts/fear.ppf")
        self.font_menu = pixel_font.load("/system/assets/fonts/nope.ppf")
        self.font_medium = pixel_font.load("/system/assets/fonts/futile.ppf")
        self.font_large = pixel_font.load("/system/assets/fonts/ignore.ppf")
        self.pet = PetRenderer()
        screen.antialias = image.X4
        print("[stockpet] Display initialized, fonts loaded")

    def center_x(self, text):
        w = screen.measure_text(text)[0]
        return (screen.width - w) // 2

    def dim(self, rgb_tuple, low_battery=False):
        if low_battery:
            return tuple(int(c * 0.85) for c in rgb_tuple)
        return rgb_tuple

    def draw_battery(self, low_battery=False):
        if is_charging():
            battery_level = (io.ticks / 20) % 100
        else:
            battery_level = get_battery_level()
        pos_x = screen.width - 22
        pos_y = 2
        width = 16
        height = 8
        if is_charging():
            bat_color = COLORS["after_hours"]
        elif battery_level > 50:
            bat_color = COLORS["up"]
        elif battery_level > 20:
            bat_color = COLORS["neutral"]
        else:
            bat_color = COLORS["down"]
        bat_color = self.dim(bat_color, low_battery)
        screen.pen = rgb(*bat_color)
        screen.rectangle(pos_x, pos_y, width, height)
        screen.rectangle(pos_x + width, pos_y + 2, 2, 4)
        screen.pen = rgb(*COLORS["bg"])
        screen.rectangle(pos_x + 1, pos_y + 1, width - 2, height - 2)
        fill_width = int((width - 4) * battery_level / 100)
        screen.pen = rgb(*bat_color)
        screen.rectangle(pos_x + 2, pos_y + 2, fill_width, height - 4)

    def draw_splash(self, message, progress, total):
        screen.pen = rgb(*COLORS["bg"])
        screen.clear()
        screen.font = self.font_medium
        screen.pen = rgb(*COLORS["text"])
        title = "StockPet"
        screen.text(title, self.center_x(title), 20)
        screen.font = self.font_small
        screen.pen = rgb(*COLORS["dim"])
        screen.text(message, self.center_x(message), 55)
        progress_str = f"({progress}/{total})"
        screen.text(progress_str, self.center_x(progress_str), 75)
        bar_width = 120
        bar_x = (screen.width - bar_width) // 2
        bar_y = 95
        bar_height = 8
        screen.pen = rgb(*COLORS["dim"])
        screen.rectangle(bar_x, bar_y, bar_width, bar_height)
        fill_width = int(bar_width * progress / total) if total > 0 else 0
        screen.pen = rgb(*COLORS["up"])
        screen.rectangle(bar_x, bar_y, fill_width, bar_height)

    def render_pet(self, ticker, data, market_open, session, holiday,
                   mood_key, mood_text, mood_index, settings, low_battery=False):
        current_ms = time.ticks_ms()
        change = data.get("change", 0)
        price = data.get("price", 0)
        change_percent = data.get("change_percent", 0)
        has_error = data.get("error", False)

        # Background
        if not market_open:
            bg = self.dim(COLORS["sleep_bg"], low_battery)
        else:
            bg = self.dim(COLORS["bg"], low_battery)
        screen.pen = rgb(*bg)
        screen.clear()

        # Top bar: ticker + price
        screen.font = self.font_small
        screen.pen = rgb(*self.dim(COLORS["text"], low_battery))
        screen.text(ticker, 4, 2)
        price_str = fmt_price(price)
        pw = screen.measure_text(price_str)[0]
        screen.text(price_str, screen.width - pw - 24, 2)

        # Change percent
        pct_str = fmt_percent(change_percent)
        if change > 0:
            pct_color = COLORS["up"]
        elif change < 0:
            pct_color = COLORS["down"]
        else:
            pct_color = COLORS["neutral"]
        screen.pen = rgb(*self.dim(pct_color, low_battery))
        screen.font = self.font_menu
        screen.text(pct_str, self.center_x(pct_str), 14)

        # Battery
        if settings.get("show_battery", True):
            self.draw_battery(low_battery)

        # The Pet
        self.pet.draw(change_percent, market_open, mood_key, current_ms, low_battery)

        # Ground line
        screen.pen = rgb(*self.dim(COLORS["dim"], low_battery))
        screen.rectangle(20, 88, screen.width - 40, 1)

        # Mood text
        screen.font = self.font_menu
        screen.pen = rgb(*self.dim(pct_color if market_open else COLORS["zzz"], low_battery))
        screen.text(mood_text, self.center_x(mood_text), 94)

        # Navigation hint
        screen.pen = rgb(*self.dim(COLORS["dim"], low_battery))
        nav = f"< {mood_index + 1}/{len(STOCKS)} >"
        screen.text(nav, self.center_x(nav), 108)

        if has_error:
            screen.pen = rgb(*self.dim(COLORS["error"], low_battery))
            screen.text("! data error", self.center_x("! data error"), 108)

    def render_settings(self, wifi_connected, last_update, market_open,
                        settings, selected_index, low_battery=False):
        screen.pen = rgb(*self.dim(COLORS["bg"], low_battery))
        screen.clear()
        self.draw_battery(low_battery)
        screen.font = self.font_medium
        screen.pen = rgb(*self.dim(COLORS["text"], low_battery))
        title = "Settings"
        screen.text(title, self.center_x(title), 2)
        screen.font = self.font_menu
        line_height = 11
        dim_options = {0: "Never", 5: "5 sec", 20: "20 sec", 40: "40 sec", 60: "60 sec"}
        dim_value = settings.get("auto_dim", 0)
        dim_text = dim_options.get(dim_value, "Never")
        menu_items = [
            ("WiFi", get_wifi_ssid() if wifi_connected else "Disconnected", False),
            ("IP", get_ip_address(), False),
            ("Updated", fmt_time_ago(time.ticks_diff(time.ticks_ms(), last_update)), False),
            ("Battery", f"{int(get_battery_level())}%" + (" chrg" if is_charging() else ""), False),
            ("Market", "OPEN" if market_open else "CLOSED", False),
            ("---", "", False),
            ("Show Battery", "ON" if settings.get("show_battery", True) else "OFF", True),
            ("Case Light", "ON" if settings.get("case_light", True) else "OFF", True),
            ("Auto Dim", dim_text, True),
            ("Auto Cycle", "ON" if settings.get("auto_cycle", False) else "OFF", True),
            ("Refresh All", "Press A", True),
        ]
        menu_top = 20
        menu_bottom = 98
        visible_height = menu_bottom - menu_top
        max_visible = visible_height // line_height
        scroll_offset = 0
        if selected_index >= max_visible:
            scroll_offset = selected_index - max_visible + 1
        y_pos = menu_top
        for i, (label, value, is_toggle) in enumerate(menu_items):
            if i < scroll_offset:
                continue
            if y_pos > menu_bottom:
                break
            if label == "---":
                screen.pen = rgb(*self.dim(COLORS["dim"], low_battery))
                screen.rectangle(8, y_pos + 3, screen.width - 16, 1)
                y_pos += 8
                continue
            if i == selected_index:
                screen.pen = rgb(*self.dim((40, 40, 60), low_battery))
                screen.rectangle(0, y_pos - 1, screen.width, line_height)
                screen.pen = rgb(*self.dim(COLORS["text"], low_battery))
                screen.text(">", 2, y_pos)
            if is_toggle and i == selected_index:
                screen.pen = rgb(*self.dim(COLORS["text"], low_battery))
            elif is_toggle:
                screen.pen = rgb(*self.dim(COLORS["after_hours"], low_battery))
            else:
                screen.pen = rgb(*self.dim(COLORS["dim"], low_battery))
            screen.text(f"{label}:", 12, y_pos)
            if label == "WiFi":
                col = COLORS["up"] if wifi_connected else COLORS["down"]
            elif label == "Market":
                col = COLORS["up"] if market_open else COLORS["after_hours"]
            elif label == "Show Battery":
                col = COLORS["up"] if settings.get("show_battery", True) else COLORS["down"]
            elif label == "Case Light":
                col = COLORS["up"] if settings.get("case_light", True) else COLORS["down"]
            elif label == "Auto Dim":
                col = COLORS["neutral"] if settings.get("auto_dim", 0) == 0 else COLORS["after_hours"]
            elif label == "Auto Cycle":
                col = COLORS["up"] if settings.get("auto_cycle", False) else COLORS["down"]
            elif label == "Refresh All":
                col = COLORS["neutral"]
            else:
                col = COLORS["text"]
            screen.pen = rgb(*self.dim(col, low_battery))
            val_width = screen.measure_text(value)[0]
            screen.text(value, screen.width - val_width - 6, y_pos)
            y_pos += line_height
        if scroll_offset > 0:
            screen.pen = rgb(*self.dim(COLORS["dim"], low_battery))
            screen.text("^", screen.width // 2 - 3, menu_top - 4)
        if scroll_offset + max_visible < len(menu_items):
            screen.pen = rgb(*self.dim(COLORS["dim"], low_battery))
            screen.text("v", screen.width // 2 - 3, menu_bottom + 2)
        screen.pen = rgb(*self.dim(COLORS["dim"], low_battery))
        footer = "UP/DN:Nav A:Select B:Back"
        screen.text(footer, self.center_x(footer), 108)


# =============================================================================
# App Controller
# =============================================================================

class StockPetApp:
    CYCLE_INTERVAL_MS = 30_000

    def __init__(self):
        print("[stockpet] Initializing app...")
        self.display = PetDisplay()
        self.mode = AppMode.STARTUP
        self.current_index = 0
        self.wifi_connected = False
        self.market_open = False
        self.session = None
        self.holiday = None
        self.settings = {
            "show_battery": True,
            "case_light": True,
            "auto_dim": 0,
            "auto_cycle": False,
        }
        self.dim_options = [0, 5, 20, 40, 60]
        self.last_activity_ms = time.ticks_ms()
        self.is_dimmed = False
        self.last_cycle_ms = time.ticks_ms()
        self.settings_index = 0
        self.settings_menu_count = 11
        self.stock_data = {ticker: get_mock_data(ticker) for ticker in STOCKS}
        for d in self.stock_data.values():
            d["last_fetch_ms"] = 0
        self.startup_index = 0
        self.startup_connecting = True
        self.wifi_attempts = 0
        self.wifi_max_attempts = 10
        self.wifi_gave_up = False
        self.last_background_check = 0
        self.background_index = 0
        self.refreshing = False
        self.mood_text_index = 0
        self.last_mood_change = time.ticks_ms()
        print("[stockpet] Init complete")

    def current_ticker(self):
        if self.current_index >= len(STOCKS):
            self.current_index = 0
        return STOCKS[self.current_index]

    def current_data(self):
        return self.stock_data.get(self.current_ticker(), get_mock_data(self.current_ticker()))

    def handle_input(self):
        if self.mode == AppMode.STARTUP:
            return
        any_button = (io.BUTTON_UP in io.pressed or io.BUTTON_DOWN in io.pressed or
                      io.BUTTON_A in io.pressed or io.BUTTON_B in io.pressed or
                      io.BUTTON_C in io.pressed)
        if any_button:
            self.last_activity_ms = time.ticks_ms()
            if self.is_dimmed:
                self.is_dimmed = False
                display.backlight(1.0)

        if self.mode == AppMode.INFO:
            if io.BUTTON_UP in io.pressed:
                self.settings_index = (self.settings_index - 1) % self.settings_menu_count
                if self.settings_index == 5:
                    self.settings_index = 4
            if io.BUTTON_DOWN in io.pressed:
                self.settings_index = (self.settings_index + 1) % self.settings_menu_count
                if self.settings_index == 5:
                    self.settings_index = 6
            if io.BUTTON_A in io.pressed:
                if self.settings_index == 6:
                    self.settings["show_battery"] = not self.settings["show_battery"]
                    print(f"[stockpet] Show battery: {self.settings['show_battery']}")
                elif self.settings_index == 7:
                    self.settings["case_light"] = not self.settings["case_light"]
                    print(f"[stockpet] Case light: {self.settings['case_light']}")
                elif self.settings_index == 8:
                    current = self.settings.get("auto_dim", 0)
                    idx = self.dim_options.index(current) if current in self.dim_options else 0
                    self.settings["auto_dim"] = self.dim_options[(idx + 1) % len(self.dim_options)]
                    print(f"[stockpet] Auto dim: {self.settings['auto_dim']}")
                elif self.settings_index == 9:
                    self.settings["auto_cycle"] = not self.settings["auto_cycle"]
                    self.last_cycle_ms = time.ticks_ms()
                    print(f"[stockpet] Auto cycle: {self.settings['auto_cycle']}")
                elif self.settings_index == 10:
                    print("[stockpet] Force refresh all")
                    self.force_refresh_all()
            if io.BUTTON_B in io.pressed:
                self.mode = AppMode.NORMAL
                print("[stockpet] Back to pet view")
            return

        if io.BUTTON_UP in io.pressed:
            self.current_index = (self.current_index - 1) % len(STOCKS)
            self.last_cycle_ms = time.ticks_ms()
            self.mood_text_index = 0
            print(f"[stockpet] Switched to {self.current_ticker()}")
        if io.BUTTON_DOWN in io.pressed:
            self.current_index = (self.current_index + 1) % len(STOCKS)
            self.last_cycle_ms = time.ticks_ms()
            self.mood_text_index = 0
            print(f"[stockpet] Switched to {self.current_ticker()}")
        if io.BUTTON_B in io.pressed:
            self.settings_index = 6
            self.mode = AppMode.INFO
            print("[stockpet] Entering settings")
        if io.BUTTON_C in io.pressed:
            print(f"[stockpet] Force refresh {self.current_ticker()}")
            result = fetch_stock_data(self.current_ticker())
            if result:
                self.stock_data[self.current_ticker()] = result

    def force_refresh_all(self):
        for ticker in STOCKS:
            result = fetch_stock_data(ticker)
            if result:
                self.stock_data[ticker] = result
            else:
                self.stock_data[ticker]["error"] = True

    def do_startup(self):
        if self.startup_connecting:
            if self.wifi_gave_up:
                self.display.draw_splash("WiFi failed!  A:Retry  B:Offline", 0, len(STOCKS))
                if io.BUTTON_A in io.pressed:
                    self.wifi_attempts = 0
                    self.wifi_gave_up = False
                    print("[stockpet] Retrying WiFi...")
                elif io.BUTTON_B in io.pressed:
                    self.wifi_connected = False
                    self.startup_connecting = False
                    print("[stockpet] Going offline, mock data")
                return
            wifi.tick()
            if wifi.is_connected() or wifi.connect():
                self.wifi_connected = True
                self.startup_connecting = False
                print("[stockpet] WiFi connected!")
            else:
                self.wifi_attempts += 1
                if self.wifi_attempts >= self.wifi_max_attempts:
                    self.wifi_gave_up = True
                    print("[stockpet] WiFi gave up")
                else:
                    self.display.draw_splash(
                        f"Connecting WiFi... ({self.wifi_attempts}/{self.wifi_max_attempts})",
                        0, len(STOCKS))
                return
        if self.startup_index < len(STOCKS):
            ticker = STOCKS[self.startup_index]
            self.display.draw_splash(f"Fetching {ticker}...", self.startup_index, len(STOCKS))
            result = fetch_stock_data(ticker)
            if result:
                self.stock_data[ticker] = result
            else:
                self.stock_data[ticker]["error"] = True
            self.startup_index += 1
        else:
            self.mode = AppMode.NORMAL
            print("[stockpet] Startup complete, entering pet view")

    def maybe_refresh_current(self):
        ticker = self.current_ticker()
        data = self.current_data()
        if is_data_fresh(data, self.market_open):
            return
        if is_data_stale(data, self.market_open):
            self.refreshing = True
            result = fetch_stock_data(ticker)
            if result:
                self.stock_data[ticker] = result
            else:
                self.stock_data[ticker]["error"] = True
            self.refreshing = False

    def maybe_background_fetch(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_background_check) < BACKGROUND_CHECK_MS:
            return
        self.last_background_check = now
        current = self.current_ticker()
        for i in range(len(STOCKS)):
            idx = (self.background_index + i) % len(STOCKS)
            ticker = STOCKS[idx]
            if ticker == current:
                continue
            data = self.stock_data.get(ticker)
            if is_data_stale(data, self.market_open):
                result = fetch_stock_data(ticker)
                if result:
                    self.stock_data[ticker] = result
                else:
                    self.stock_data[ticker]["error"] = True
                self.background_index = (idx + 1) % len(STOCKS)
                break

    def update_case_light(self):
        if not self.settings.get("case_light", True):
            for led in range(4):
                set_case_led(led, 0)
            return
        change = self.current_data().get("change", 0)
        if not self.market_open:
            set_case_led(0, 0); set_case_led(1, 0)
            set_case_led(2, 1); set_case_led(3, 1)
        elif change > 0:
            for led in range(4):
                set_case_led(led, 1)
        elif change < 0:
            set_case_led(0, 1); set_case_led(1, 1)
            set_case_led(2, 0); set_case_led(3, 0)
        else:
            set_case_led(0, 1); set_case_led(1, 0)
            set_case_led(2, 1); set_case_led(3, 0)

    def update_auto_dim(self):
        dim_seconds = self.settings.get("auto_dim", 0)
        if dim_seconds == 0:
            if self.is_dimmed:
                self.is_dimmed = False
                display.backlight(1.0)
            return
        idle_ms = time.ticks_diff(time.ticks_ms(), self.last_activity_ms)
        idle_seconds = idle_ms // 1000
        if idle_seconds >= dim_seconds and not self.is_dimmed:
            self.is_dimmed = True
            display.backlight(0.3)
            print("[stockpet] Display dimmed")
        elif idle_seconds < dim_seconds and self.is_dimmed:
            self.is_dimmed = False
            display.backlight(1.0)
            print("[stockpet] Display woken")

    def update_auto_cycle(self):
        if not self.settings.get("auto_cycle", False):
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_cycle_ms) < self.CYCLE_INTERVAL_MS:
            return
        self.last_cycle_ms = now
        self.current_index = (self.current_index + 1) % len(STOCKS)
        self.mood_text_index = 0
        print(f"[stockpet] Auto-cycled to {self.current_ticker()}")

    def update_mood_text(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_mood_change) >= MOOD_CHANGE_MS:
            self.mood_text_index += 1
            self.last_mood_change = now

    def update(self):
        wifi.tick()
        self.handle_input()
        self.market_open, self.session, self.holiday = fetch_market_status()
        self.wifi_connected = wifi.is_connected()
        low_battery = not is_charging() and get_battery_level() < 20
        if self.mode == AppMode.STARTUP:
            self.do_startup()
            return
        self.update_auto_dim()
        if self.mode == AppMode.INFO:
            latest = max((d.get("last_fetch_ms", 0) for d in self.stock_data.values()), default=0)
            self.display.render_settings(
                self.wifi_connected, latest, self.market_open,
                self.settings, self.settings_index, low_battery)
            self.update_case_light()
            return
        self.update_auto_cycle()
        self.update_mood_text()
        self.maybe_refresh_current()
        self.maybe_background_fetch()
        data = self.current_data()
        change_percent = data.get("change_percent", 0)
        mood_key = get_mood_key(change_percent, self.market_open)
        mood_text = pick_mood_text(mood_key, self.mood_text_index)
        self.display.render_pet(
            self.current_ticker(), data, self.market_open,
            self.session, self.holiday,
            mood_key, mood_text, self.current_index,
            self.settings, low_battery)
        self.update_case_light()


# =============================================================================
# Entry Points
# =============================================================================

_app = None

def init():
    global _app
    _app = StockPetApp()

def update():
    _app.update()

def on_exit():
    for led in range(4):
        set_case_led(led, 0)
    display.backlight(1.0)
    print("[stockpet] App exited, LEDs off, backlight restored")

if __name__ == "__main__":
    run(update, init=init, on_exit=on_exit)
