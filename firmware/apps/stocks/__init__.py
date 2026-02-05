# Stocks app for Tufty2350
# Smart fetching + backlight + polish + LUDICROUS MODE (Spaceballs warp when up, slow drift when down)

APP_DIR = "/system/apps/stocks"

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
from easing import easeOutSine

try:
    from usermessage import user_message
except ImportError:
    def user_message(title, lines):
        pass


# =============================================================================
# Configuration
# =============================================================================

FRESH_MS = 60_000
STALE_MS = 300_000
MARKET_CLOSED_STALE_MS = 900_000
BACKGROUND_CHECK_MS = 60_000

ANIMATION_PERIOD_MS = 2_000

COLORS = {
    "up": (0, 255, 0),
    "down": (255, 0, 0),
    "neutral": (200, 200, 200),
    "bg": (0, 0, 0),
    "text": (255, 255, 255),
    "dim": (100, 100, 100),
    "after_hours": (100, 100, 255),
    "error": (255, 100, 100),
    "ludicrous": (255, 240, 100),   # bright yellow-white streaks
    "drift": (80, 80, 180),         # slow wavy blue-purple
}

MARKET_OPEN_HOUR = 9.5
MARKET_CLOSE_HOUR = 16.0

try:
    LOCAL_TZ = secrets.TIMEZONE
except AttributeError:
    LOCAL_TZ = -8
EST_OFFSET = LOCAL_TZ - (-5)


# =============================================================================
# Load Configuration
# =============================================================================

try:
    STOCKS = secrets.STOCKS
except AttributeError:
    STOCKS = ["TSLA", "PLTR", "SPY", "QQQ"]

try:
    FINNHUB_KEY = secrets.FINNHUB_KEY
except AttributeError:
    FINNHUB_KEY = None


# =============================================================================
# Mock Data
# =============================================================================

MOCK_DATA = {
    "TSLA": {"price": 420.00, "change": 5.25, "change_percent": 1.26},
    "PLTR": {"price": 35.50, "change": 0.75, "change_percent": 2.15},
    "SPY":  {"price": 385.20, "change": -2.10, "change_percent": -0.54},
    "QQQ":  {"price": 315.75, "change": 3.45, "change_percent": 1.10},
}

def get_mock_data(ticker):
    base = MOCK_DATA.get(ticker, MOCK_DATA["TSLA"])
    return {
        "price": base["price"],
        "change": base["change"],
        "change_percent": base["change_percent"],
        "last_fetch_ms": time.ticks_ms(),
        "error": False,
    }


# =============================================================================
# App Modes / Sizes
# =============================================================================

class AppMode:
    STARTUP = 0
    NORMAL = 1
    INFO = 2

class TickerSize:
    LARGE = 0
    LARGER = 1
    EVEN_LARGER = 2
    GARGANTUAN = 3
    _COUNT = 4


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
    if _market_cache["is_open"] is not None and now - _market_cache["last_fetch"] < MARKET_CACHE_MS:
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
        return is_open, session, holiday
    except Exception:
        return is_market_open_fallback()


# =============================================================================
# Helpers
# =============================================================================

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


# =============================================================================
# Animation
# =============================================================================

def get_pulse_alpha(current_ms, period=ANIMATION_PERIOD_MS):
    phase = (current_ms % period) / period
    return 0.5 + easeOutSine(phase) * 0.5

def blend_color(base_rgb, alpha):
    return tuple(int(c * alpha) for c in base_rgb)

def rgb(r, g, b):
    return color.rgb(r, g, b)


# =============================================================================
# Data Fetching
# =============================================================================

def fetch_stock_data(ticker):
    if FINNHUB_KEY is None:
        return get_mock_data(ticker)
    try:
        import urequests
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}"
        resp = urequests.get(url, timeout=10)
        if resp.status_code != 200:
            resp.close()
            return None
        data = json.loads(resp.text)
        resp.close()
        if data.get("c", 0) == 0:
            return None
        return {
            "price": data["c"],
            "change": data.get("d", 0) or 0,
            "change_percent": data.get("dp", 0) or 0,
            "last_fetch_ms": time.ticks_ms(),
            "error": False,
        }
    except Exception:
        return None


def get_data_age(stock_data):
    if stock_data is None:
        return 999999999
    return time.ticks_ms() - stock_data.get("last_fetch_ms", 0)

def is_data_fresh(stock_data, market_open):
    return get_data_age(stock_data) < FRESH_MS

def is_data_stale(stock_data, market_open):
    threshold = STALE_MS if market_open else MARKET_CLOSED_STALE_MS
    return get_data_age(stock_data) > threshold


# =============================================================================
# Display
# =============================================================================

class StockDisplay:
    def __init__(self):
        self.font_small = pixel_font.load("/system/assets/fonts/fear.ppf")
        self.font_menu = pixel_font.load("/system/assets/fonts/nope.ppf")
        self.font_medium = pixel_font.load("/system/assets/fonts/futile.ppf")
        self.font_large = pixel_font.load("/system/assets/fonts/ignore.ppf")
        screen.antialias = image.X4

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
        pos_y = 4
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

    def draw_ludicrous(self, current_ms, change, low_battery=False):
        """Spaceballs-style background: fast plaid warp when up, slow wavy drift when down."""
        if change == 0:
            return

        if change > 0:
            # LUDICROUS SPEED – fast crossing diagonal streaks
            phase = (current_ms // 6) % (screen.width * 2)
            col = self.dim(COLORS["ludicrous"], low_battery)
            screen.pen = rgb(*col)
            for i in range(28):
                offset = (i * 14 + phase) % (screen.width + 80) - 40
                screen.line(offset, 0, offset + 35, screen.height)
                screen.line(offset + 12, 0, offset - 18, screen.height)  # plaid cross
        else:
            # Slow disorienting drift
            phase = (current_ms // 55) % 360
            col = self.dim(COLORS["drift"], low_battery)
            screen.pen = rgb(*col)
            for i in range(18):
                y = (i * 14 + int(phase * 0.7)) % screen.height
                wave = int(12 * math.sin((y + phase) * 0.04))
                screen.rectangle(wave, y, screen.width - wave * 2, 4)

    def draw_splash(self, message, progress, total):
        screen.pen = rgb(*COLORS["bg"])
        screen.clear()

        screen.font = self.font_medium
        screen.pen = rgb(*COLORS["text"])
        title = "STONKS"
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

    def render_stock(self, ticker, data, market_open, session, holiday, ticker_size, refreshing=False, settings=None, low_battery=False):
        if settings is None:
            settings = {}

        current_ms = time.ticks_ms()
        change = data.get("change", 0)
        price = data.get("price", 0)
        change_percent = data.get("change_percent", 0)
        has_error = data.get("error", False)

        # Background
        if not market_open:
            base_bg = COLORS["bg"]
        else:
            alpha = get_pulse_alpha(current_ms)
            if change > 0:
                base = (30, 60, 30)
            elif change < 0:
                base = (60, 30, 30)
            else:
                base = (40, 40, 40)
            base_bg = blend_color(base, alpha)
        bg = self.dim(base_bg, low_battery)
        screen.pen = rgb(*bg)
        screen.clear()

        # Ludicrous mode behind everything
        if settings.get("ludicrous", False) and market_open:
            self.draw_ludicrous(current_ms, change, low_battery)

        if settings.get("show_battery", True):
            self.draw_battery(low_battery)

        # Price color
        price_base = COLORS["text"] if market_open else blend_color(COLORS["text"], get_pulse_alpha(current_ms))
        price_color = self.dim(price_base, low_battery)

        price_str = fmt_price(price)

        # Short change string
        change_str = f"{fmt_change(change)} ({fmt_percent(change_percent)})"
        if change > 0:
            change_color = self.dim(COLORS["up"], low_battery)
        elif change < 0:
            change_color = self.dim(COLORS["down"], low_battery)
        else:
            change_color = self.dim(COLORS["neutral"], low_battery)

        # Market status
        if holiday:
            status_text = holiday
            status_color = self.dim(COLORS["after_hours"], low_battery)
        elif session == "pre-market":
            status_text = "Pre-Market"
            status_color = self.dim(COLORS["neutral"], low_battery)
        elif session == "post-market":
            status_text = "After Hours"
            status_color = self.dim(COLORS["after_hours"], low_battery)
        elif market_open:
            status_text = "Market OPEN"
            status_color = self.dim(COLORS["up"], low_battery)
        else:
            status_text = "Market CLOSED"
            status_color = self.dim(COLORS["after_hours"], low_battery)

        # Layouts
        if ticker_size == TickerSize.LARGE:
            screen.font = self.font_medium
            screen.pen = rgb(*self.dim(COLORS["text"], low_battery))
            screen.text(ticker, self.center_x(ticker), 10)
            screen.pen = rgb(*price_color)
            screen.text(price_str, self.center_x(price_str), 40)
            screen.font = self.font_small
            screen.pen = rgb(*change_color)
            screen.text(change_str, self.center_x(change_str), 70)
            screen.pen = rgb(*status_color)
            screen.text(status_text, self.center_x(status_text), 95)

        elif ticker_size == TickerSize.LARGER:
            screen.font = self.font_large
            screen.pen = rgb(*self.dim(COLORS["text"], low_battery))
            screen.text(ticker, self.center_x(ticker), 8)
            screen.font = self.font_medium
            screen.pen = rgb(*price_color)
            screen.text(price_str, self.center_x(price_str), 45)
            screen.font = self.font_small
            screen.pen = rgb(*change_color)
            screen.text(change_str, self.center_x(change_str), 75)
            screen.pen = rgb(*status_color)
            screen.text(status_text, self.center_x(status_text), 95)

        elif ticker_size == TickerSize.EVEN_LARGER:
            screen.font = self.font_large
            screen.pen = rgb(*self.dim(COLORS["text"], low_battery))
            screen.text(ticker, self.center_x(ticker), 10)
            screen.pen = rgb(*price_color)
            screen.text(price_str, self.center_x(price_str), 50)
            screen.font = self.font_small
            screen.pen = rgb(*change_color)
            screen.text(change_str, self.center_x(change_str), 90)

        else:  # GARGANTUAN
            screen.font = self.font_large
            screen.pen = rgb(*self.dim(COLORS["text"], low_battery))
            screen.text(ticker, self.center_x(ticker), 30)
            screen.font = self.font_medium
            screen.pen = rgb(*price_color)
            screen.text(price_str, self.center_x(price_str), 75)   # bumped up

        if refreshing:
            screen.font = self.font_small
            screen.pen = rgb(*self.dim(COLORS["dim"], low_battery))
            screen.text("refreshing...", self.center_x("refreshing..."), 110)

        if has_error:
            screen.font = self.font_small
            screen.pen = rgb(*self.dim(COLORS["error"], low_battery))
            screen.text("! retry soon", self.center_x("! retry soon"), 110)

    def render_settings(self, wifi_connected, last_update, market_open, settings, selected_index, low_battery=False):
        screen.pen = rgb(*self.dim(COLORS["bg"], low_battery))
        screen.clear()

        self.draw_battery(low_battery)

        screen.font = self.font_medium
        screen.pen = rgb(*self.dim(COLORS["text"], low_battery))
        title = "Settings"
        screen.text(title, self.center_x(title), 2)

        screen.font = self.font_menu
        line_height = 11
        
        # Auto dim display text
        dim_options = {0: "Never", 5: "5 sec", 20: "20 sec", 40: "40 sec", 60: "60 sec"}
        dim_value = settings.get("auto_dim", 0)
        dim_text = dim_options.get(dim_value, "Never")

        menu_items = [
            ("WiFi", get_wifi_ssid() if wifi_connected else "Disconnected", False),
            ("IP", get_ip_address(), False),
            ("Updated", fmt_time_ago(time.ticks_ms() - last_update), False),
            ("Battery", f"{int(get_battery_level())}%" + (" chrg" if is_charging() else ""), False),
            ("Market", "OPEN" if market_open else "CLOSED", False),
            ("---", "", False),
            ("Show Battery", "ON" if settings.get("show_battery", True) else "OFF", True),
            ("Case Light", "ON" if settings.get("case_light", True) else "OFF", True),
            ("Auto Dim", dim_text, True),
            ("Auto Cycle", "ON" if settings.get("auto_cycle", False) else "OFF", True),
            ("Ludicrous Mode", "ON" if settings.get("ludicrous", False) else "OFF", True),
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
            elif label == "Ludicrous Mode":
                col = COLORS["up"] if settings.get("ludicrous", False) else COLORS["down"]
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
        screen.text(footer, self.center_x(footer), 110)

        screen.font = self.font_small
        screen.pen = rgb(*self.dim(COLORS["dim"], low_battery))
        now = time.localtime()
        clock_str = f"{now[3]:02d}:{now[4]:02d}"
        clock_w = screen.measure_text(clock_str)[0]
        screen.text(clock_str, screen.width - clock_w - 8, 110)


# =============================================================================
# App Controller
# =============================================================================

class StocksApp:
    def __init__(self):
        self.display = StockDisplay()
        self.mode = AppMode.STARTUP
        self.ticker_size = TickerSize.LARGE
        self.current_index = 0
        self.wifi_connected = False
        self.market_open = False
        self.session = None
        self.holiday = None

        self.settings = {
            "show_battery": True,
            "case_light": True,
            "auto_dim": 0,               # 0=Never, 5/20/40/60 seconds
            "auto_cycle": False,         # Carousel mode - cycle through tickers
            "ludicrous": False,          # default OFF – it's fun but optional
        }
        
        # Auto dim options cycle: Never -> 5 -> 20 -> 40 -> 60 -> Never
        self.dim_options = [0, 5, 20, 40, 60]
        
        # Track last activity for auto-dim
        self.last_activity_ms = time.ticks_ms()
        self.is_dimmed = False
        
        # Auto cycle timing
        self.last_cycle_ms = time.ticks_ms()
        self.CYCLE_INTERVAL_MS = 30_000  # 30 seconds between cycles

        self.settings_index = 0
        self.settings_menu_count = 12  # Added Auto Cycle option

        self.stock_data = {ticker: get_mock_data(ticker) for ticker in STOCKS}
        for d in self.stock_data.values():
            d["last_fetch_ms"] = 0

        self.startup_index = 0
        self.startup_connecting = True

        self.last_background_check = 0
        self.background_index = 0
        self.refreshing = False

    def current_ticker(self):
        if self.current_index >= len(STOCKS):
            self.current_index = 0
        return STOCKS[self.current_index]

    def current_data(self):
        return self.stock_data.get(self.current_ticker(), get_mock_data(self.current_ticker()))

    def handle_input(self):
        if self.mode == AppMode.STARTUP:
            return

        # Track activity for auto-dim (any button press resets timer)
        any_button = (io.BUTTON_UP in io.pressed or io.BUTTON_DOWN in io.pressed or 
                      io.BUTTON_A in io.pressed or io.BUTTON_B in io.pressed)
        if any_button:
            self.last_activity_ms = time.ticks_ms()
            # Wake up display if dimmed
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
                elif self.settings_index == 7:
                    self.settings["case_light"] = not self.settings["case_light"]
                elif self.settings_index == 8:          # Auto Dim - cycle through options
                    current = self.settings.get("auto_dim", 0)
                    idx = self.dim_options.index(current) if current in self.dim_options else 0
                    self.settings["auto_dim"] = self.dim_options[(idx + 1) % len(self.dim_options)]
                elif self.settings_index == 9:          # Auto Cycle
                    self.settings["auto_cycle"] = not self.settings["auto_cycle"]
                    self.last_cycle_ms = time.ticks_ms()  # Reset cycle timer
                elif self.settings_index == 10:         # Ludicrous Mode
                    self.settings["ludicrous"] = not self.settings["ludicrous"]
                elif self.settings_index == 11:
                    self.force_refresh_all()

            if io.BUTTON_B in io.pressed:
                self.mode = AppMode.NORMAL
            return

        if io.BUTTON_UP in io.pressed:
            self.current_index = (self.current_index - 1) % len(STOCKS)
            self.last_cycle_ms = time.ticks_ms()  # Reset cycle timer on manual nav
        if io.BUTTON_DOWN in io.pressed:
            self.current_index = (self.current_index + 1) % len(STOCKS)
            self.last_cycle_ms = time.ticks_ms()  # Reset cycle timer on manual nav
        if io.BUTTON_A in io.pressed:
            self.ticker_size = (self.ticker_size + 1) % TickerSize._COUNT
        if io.BUTTON_B in io.pressed:
            self.settings_index = 6
            self.mode = AppMode.INFO

    def force_refresh_all(self):
        for ticker in STOCKS:
            result = fetch_stock_data(ticker)
            if result:
                self.stock_data[ticker] = result
            else:
                self.stock_data[ticker]["error"] = True

    def do_startup(self):
        if self.startup_connecting:
            wifi.tick()
            if wifi.is_connected() or wifi.connect():
                self.wifi_connected = True
                self.startup_connecting = False
            else:
                self.display.draw_splash("Connecting WiFi...", 0, len(STOCKS))
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
        if now - self.last_background_check < BACKGROUND_CHECK_MS:
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
        """Update the 4-zone rear case LEDs based on stock status."""
        if not self.settings.get("case_light", True):
            # Turn off all case LEDs
            for led in range(4):
                set_case_led(led, 0)
            return
        
        change = self.current_data().get("change", 0)
        
        # Light up LEDs based on market/stock status
        # LEDs are mono (on/off), so we use patterns
        if not self.market_open:
            # After hours: subtle glow (bottom LEDs only)
            set_case_led(0, 0)  # TOP_LEFT
            set_case_led(1, 0)  # TOP_RIGHT
            set_case_led(2, 1)  # BOTTOM_RIGHT
            set_case_led(3, 1)  # BOTTOM_LEFT
        elif change > 0:
            # Stock up: all LEDs on
            for led in range(4):
                set_case_led(led, 1)
        elif change < 0:
            # Stock down: top LEDs only (like frown)
            set_case_led(0, 1)  # TOP_LEFT
            set_case_led(1, 1)  # TOP_RIGHT
            set_case_led(2, 0)  # BOTTOM_RIGHT
            set_case_led(3, 0)  # BOTTOM_LEFT
        else:
            # Neutral: alternating
            set_case_led(0, 1)  # TOP_LEFT
            set_case_led(1, 0)  # TOP_RIGHT
            set_case_led(2, 1)  # BOTTOM_RIGHT
            set_case_led(3, 0)  # BOTTOM_LEFT

    def update_auto_dim(self):
        """Handle auto-dimming of display backlight."""
        dim_seconds = self.settings.get("auto_dim", 0)
        
        if dim_seconds == 0:
            # Auto-dim disabled, ensure full brightness
            if self.is_dimmed:
                self.is_dimmed = False
                display.backlight(1.0)
            return
        
        # Check if enough time has passed since last activity
        idle_ms = time.ticks_ms() - self.last_activity_ms
        idle_seconds = idle_ms // 1000
        
        if idle_seconds >= dim_seconds and not self.is_dimmed:
            # Dim the display
            self.is_dimmed = True
            display.backlight(0.3)
        elif idle_seconds < dim_seconds and self.is_dimmed:
            # Activity detected, restore brightness
            self.is_dimmed = False
            display.backlight(1.0)

    def update_auto_cycle(self):
        """Handle automatic cycling through tickers (carousel mode).
        
        Simple round-robin - cycles through all tickers in order.
        """
        if not self.settings.get("auto_cycle", False):
            return
        
        now = time.ticks_ms()
        if now - self.last_cycle_ms < self.CYCLE_INTERVAL_MS:
            return
        
        # Time to cycle - just go to next ticker
        self.last_cycle_ms = now
        self.current_index = (self.current_index + 1) % len(STOCKS)

    def update(self):
        wifi.tick()
        self.handle_input()

        self.market_open, self.session, self.holiday = fetch_market_status()
        self.wifi_connected = wifi.is_connected()

        low_battery = not is_charging() and get_battery_level() < 20

        if self.mode == AppMode.STARTUP:
            self.do_startup()
            return

        # Handle auto-dim
        self.update_auto_dim()

        if self.mode == AppMode.INFO:
            latest = max((d.get("last_fetch_ms", 0) for d in self.stock_data.values()), default=0)
            self.display.render_settings(
                self.wifi_connected, latest, self.market_open,
                self.settings, self.settings_index, low_battery
            )
            self.update_case_light()
            return

        # Handle auto-cycle (carousel mode)
        self.update_auto_cycle()

        self.maybe_refresh_current()
        self.maybe_background_fetch()

        self.display.render_stock(
            self.current_ticker(), self.current_data(), self.market_open,
            self.session, self.holiday, self.ticker_size, self.refreshing,
            self.settings, low_battery
        )
        self.update_case_light()


# =============================================================================
# Entry Points
# =============================================================================

_app = None

def init():
    global _app
    _app = StocksApp()

def update():
    _app.update()

def on_exit():
    # Turn off case LEDs when exiting
    for led in range(4):
        set_case_led(led, 0)
    # Restore full backlight
    display.backlight(1.0)

if __name__ == "__main__":
    run(update, init=init, on_exit=on_exit)