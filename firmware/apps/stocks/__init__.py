# Stocks app for Tufty2350
# Smart fetching with splash screen and responsive UI

APP_DIR = "/system/apps/stocks"

import sys
import os
import time
import wifi
import secrets
import json

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from badgeware import run, State, get_battery_level, is_charging
from easing import easeOutSine

try:
    from usermessage import user_message
except ImportError:
    def user_message(title, lines):
        pass


# =============================================================================
# Configuration
# =============================================================================

# Freshness thresholds
FRESH_MS = 60_000              # 1 min - data is fresh, no fetch needed
STALE_MS = 300_000             # 5 min - background refresh
MARKET_CLOSED_STALE_MS = 900_000  # 15 min when market closed

# Background fetch timing  
BACKGROUND_CHECK_MS = 60_000   # Check one background stock per minute

# WiFi
WIFI_TIMEOUT_MS = 10_000       # 10 seconds

# Animation
ANIMATION_PERIOD_MS = 2_000
LIVE_INDICATOR_PERIOD_MS = 1_500

# Colors
COLORS = {
    "up": (0, 255, 0),
    "down": (255, 0, 0),
    "neutral": (200, 200, 200),
    "bg": (0, 0, 0),
    "text": (255, 255, 255),
    "dim": (100, 100, 100),
    "after_hours": (100, 100, 255),
    "error": (255, 100, 100),
}

# Market hours fallback
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
    print("[stocks] Finnhub key loaded OK")
except AttributeError:
    FINNHUB_KEY = None
    print("[stocks] WARNING: no FINNHUB_KEY - using mock data")


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
# App Modes
# =============================================================================

class AppMode:
    STARTUP = 0     # Splash screen during initial fetch
    NORMAL = 1      # Regular stock display
    INFO = 2        # System info screen


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

_market_cache = {
    "is_open": None,
    "session": None,
    "holiday": None,
    "last_fetch": 0,
}
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
    
    if _market_cache["is_open"] is not None:
        if now - _market_cache["last_fetch"] < MARKET_CACHE_MS:
            return (_market_cache["is_open"], _market_cache["session"], _market_cache["holiday"])
    
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
        
        _market_cache["is_open"] = is_open
        _market_cache["session"] = session
        _market_cache["holiday"] = holiday
        _market_cache["last_fetch"] = now
        
        print(f"[stocks] Market: open={is_open}, session={session}")
        return is_open, session, holiday
    except Exception as e:
        print(f"[stocks] Market status error: {e}")
        return is_market_open_fallback()


# =============================================================================
# System Info
# =============================================================================

def get_wifi_ssid():
    try:
        if wifi.is_connected():
            return getattr(secrets, "WIFI_SSID", "Connected")
        return "Not connected"
    except Exception:
        return "Unknown"

def get_ip_address():
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            return wlan.ifconfig()[0]
        return "N/A"
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
    """Fetch single stock. Returns dict with price, change, last_fetch_ms, error."""
    if FINNHUB_KEY is None:
        print(f"[stocks] No API key, mock for {ticker}")
        return get_mock_data(ticker)
    
    print(f"[stocks] Fetching {ticker}...")
    try:
        import urequests
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}"
        resp = urequests.get(url, timeout=10)
        
        if resp.status_code != 200:
            print(f"[stocks] HTTP {resp.status_code} for {ticker}")
            resp.close()
            return None  # Signal error
        
        data = json.loads(resp.text)
        resp.close()
        
        if data.get("c", 0) == 0:
            print(f"[stocks] No data for {ticker}")
            return None
        
        result = {
            "price": data["c"],
            "change": data.get("d", 0) or 0,
            "change_percent": data.get("dp", 0) or 0,
            "last_fetch_ms": time.ticks_ms(),
            "error": False,
        }
        print(f"[stocks] {ticker}: ${result['price']:.2f}")
        return result
        
    except Exception as e:
        print(f"[stocks] Error {ticker}: {e}")
        return None


def get_data_age(stock_data):
    """Get age of stock data in ms."""
    if stock_data is None:
        return 999999999
    last_fetch = stock_data.get("last_fetch_ms", 0)
    return time.ticks_ms() - last_fetch


def is_data_fresh(stock_data, market_open):
    """Check if data is fresh enough to not need refresh."""
    age = get_data_age(stock_data)
    return age < FRESH_MS


def is_data_stale(stock_data, market_open):
    """Check if data needs background refresh."""
    age = get_data_age(stock_data)
    threshold = STALE_MS if market_open else MARKET_CLOSED_STALE_MS
    return age > threshold


# =============================================================================
# Display
# =============================================================================

class StockDisplay:
    def __init__(self):
        self.font_small = pixel_font.load("/system/assets/fonts/fear.ppf")
        self.font_menu = pixel_font.load("/system/assets/fonts/nope.ppf")  # 8px, cleaner for menus
        self.font_medium = pixel_font.load("/system/assets/fonts/futile.ppf")
        self.font_large = pixel_font.load("/system/assets/fonts/ignore.ppf")
        screen.antialias = image.X4
    
    def center_x(self, text):
        w = screen.measure_text(text)[0]
        return (screen.width - w) // 2
    
    def draw_battery(self):
        """Draw battery indicator in upper right corner."""
        # Get battery level (animated if charging)
        if is_charging():
            battery_level = (io.ticks / 20) % 100
        else:
            battery_level = get_battery_level()
        
        # Position and size
        pos_x = screen.width - 22
        pos_y = 4
        width = 16
        height = 8
        
        # Choose color based on level
        if is_charging():
            bat_color = COLORS["after_hours"]  # Blue when charging
        elif battery_level > 50:
            bat_color = COLORS["up"]  # Green
        elif battery_level > 20:
            bat_color = COLORS["neutral"]  # Yellow/white
        else:
            bat_color = COLORS["down"]  # Red
        
        # Battery outline
        screen.pen = rgb(*bat_color)
        screen.rectangle(pos_x, pos_y, width, height)
        # Battery nub
        screen.rectangle(pos_x + width, pos_y + 2, 2, 4)
        
        # Clear inside
        screen.pen = rgb(*COLORS["bg"])
        screen.rectangle(pos_x + 1, pos_y + 1, width - 2, height - 2)
        
        # Fill level
        fill_width = int((width - 4) * battery_level / 100)
        screen.pen = rgb(*bat_color)
        screen.rectangle(pos_x + 2, pos_y + 2, fill_width, height - 4)
    
    def draw_splash(self, message, progress, total):
        """Draw startup splash screen."""
        screen.pen = rgb(*COLORS["bg"])
        screen.clear()
        
        # Title
        screen.font = self.font_medium
        screen.pen = rgb(*COLORS["text"])
        title = "STONKS"
        screen.text(title, self.center_x(title), 20)
        
        # Status message
        screen.font = self.font_small
        screen.pen = rgb(*COLORS["dim"])
        screen.text(message, self.center_x(message), 55)
        
        # Progress
        progress_str = f"({progress}/{total})"
        screen.text(progress_str, self.center_x(progress_str), 75)
        
        # Simple progress bar
        bar_width = 120
        bar_x = (screen.width - bar_width) // 2
        bar_y = 95
        bar_height = 8
        
        # Background
        screen.pen = rgb(*COLORS["dim"])
        screen.rectangle(bar_x, bar_y, bar_width, bar_height)
        
        # Fill
        fill_width = int(bar_width * progress / total) if total > 0 else 0
        screen.pen = rgb(*COLORS["up"])
        screen.rectangle(bar_x, bar_y, fill_width, bar_height)
    
    def render_stock(self, ticker, data, market_open, session, holiday, ticker_size, refreshing=False, settings=None):
        """Render main stock display."""
        if settings is None:
            settings = {}
        
        current_ms = time.ticks_ms()
        change = data.get("change", 0)
        price = data.get("price", 0)
        change_percent = data.get("change_percent", 0)
        has_error = data.get("error", False)
        
        # Background
        if not market_open:
            screen.pen = rgb(*COLORS["bg"])
        else:
            alpha = get_pulse_alpha(current_ms)
            if change > 0:
                base = (30, 60, 30)
            elif change < 0:
                base = (60, 30, 30)
            else:
                base = (40, 40, 40)
            screen.pen = rgb(*blend_color(base, alpha))
        screen.clear()
        
        # Battery indicator in corner (if enabled)
        if settings.get("show_battery", True):
            self.draw_battery()
        
        # Price color
        if market_open:
            price_color = COLORS["text"]
        else:
            alpha = get_pulse_alpha(current_ms)
            price_color = blend_color(COLORS["text"], alpha)
        
        price_str = fmt_price(price)
        
        # Change color
        if change > 0:
            change_color = COLORS["up"]
            direction = "UP"
        elif change < 0:
            change_color = COLORS["down"]
            direction = "DN"
        else:
            change_color = COLORS["neutral"]
            direction = "--"
        
        change_str = f"{direction} {fmt_change(change)} ({fmt_percent(change_percent)})"
        
        # Market status text
        if holiday:
            status_text = holiday
            status_color = COLORS["after_hours"]
        elif session == "pre-market":
            status_text = "Pre-Market"
            status_color = COLORS["neutral"]
        elif session == "post-market":
            status_text = "After Hours"
            status_color = COLORS["after_hours"]
        elif market_open:
            status_text = "Market OPEN"
            status_color = COLORS["up"]
        else:
            status_text = "Market CLOSED"
            status_color = COLORS["after_hours"]
        
        # Layout based on size
        if ticker_size == TickerSize.LARGE:
            screen.font = self.font_medium
            screen.pen = rgb(*COLORS["text"])
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
            screen.pen = rgb(*COLORS["text"])
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
            screen.pen = rgb(*COLORS["text"])
            screen.text(ticker, self.center_x(ticker), 10)
            
            screen.pen = rgb(*price_color)
            screen.text(price_str, self.center_x(price_str), 50)
            
            screen.font = self.font_small
            screen.pen = rgb(*change_color)
            screen.text(change_str, self.center_x(change_str), 90)
            
        else:  # GARGANTUAN
            screen.font = self.font_large
            screen.pen = rgb(*COLORS["text"])
            screen.text(ticker, self.center_x(ticker), 30)
            
            screen.font = self.font_medium
            screen.pen = rgb(*price_color)
            screen.text(price_str, self.center_x(price_str), 85)
        
        # Refreshing indicator (small text at bottom)
        if refreshing:
            screen.font = self.font_small
            screen.pen = rgb(*COLORS["dim"])
            screen.text("refreshing...", self.center_x("refreshing..."), 110)
        
        # Error indicator
        if has_error:
            screen.font = self.font_small
            screen.pen = rgb(*COLORS["error"])
            screen.text("! retry soon", self.center_x("! retry soon"), 110)
    
    def render_settings(self, wifi_connected, last_update, market_open, settings, selected_index):
        """Render interactive settings/info screen with scrolling."""
        screen.pen = rgb(*COLORS["bg"])
        screen.clear()
        
        # Battery icon in corner
        self.draw_battery()
        
        screen.font = self.font_medium
        screen.pen = rgb(*COLORS["text"])
        title = "Settings"
        screen.text(title, self.center_x(title), 2)
        
        # Use nope font (8px) for menu - fits better
        screen.font = self.font_menu
        line_height = 11
        
        # Menu items: (label, value, is_toggle)
        menu_items = [
            ("WiFi", get_wifi_ssid() if wifi_connected else "Disconnected", False),
            ("IP", get_ip_address(), False),
            ("Updated", fmt_time_ago(time.ticks_ms() - last_update), False),
            ("Battery", f"{int(get_battery_level())}%" + (" chrg" if is_charging() else ""), False),
            ("Market", "OPEN" if market_open else "CLOSED", False),
            ("---", "", False),  # Separator
            ("Show Battery", "ON" if settings.get("show_battery", True) else "OFF", True),
            ("Refresh All", "Press A", True),
        ]
        
        # Visible area
        menu_top = 20
        menu_bottom = 98
        visible_height = menu_bottom - menu_top
        max_visible = visible_height // line_height
        
        # Calculate scroll offset to keep selected item visible
        scroll_offset = 0
        if selected_index >= max_visible:
            scroll_offset = selected_index - max_visible + 1
        
        # Draw menu items
        y_pos = menu_top
        for i, (label, value, is_toggle) in enumerate(menu_items):
            # Skip items above scroll
            if i < scroll_offset:
                continue
            
            # Stop if below visible area
            if y_pos > menu_bottom:
                break
            
            # Separator
            if label == "---":
                screen.pen = rgb(*COLORS["dim"])
                screen.rectangle(8, y_pos + 3, screen.width - 16, 1)
                y_pos += 8
                continue
            
            # Selection highlight
            if i == selected_index:
                # Highlight background
                screen.pen = rgb(40, 40, 60)
                screen.rectangle(0, y_pos - 1, screen.width, line_height)
                # Arrow
                screen.pen = rgb(*COLORS["text"])
                screen.text(">", 2, y_pos)
            
            # Label color
            if is_toggle and i == selected_index:
                screen.pen = rgb(*COLORS["text"])
            elif is_toggle:
                screen.pen = rgb(*COLORS["after_hours"])
            else:
                screen.pen = rgb(*COLORS["dim"])
            
            screen.text(f"{label}:", 12, y_pos)
            
            # Value color
            if label == "WiFi":
                screen.pen = rgb(*COLORS["up"]) if wifi_connected else rgb(*COLORS["down"])
            elif label == "Market":
                screen.pen = rgb(*COLORS["up"]) if market_open else rgb(*COLORS["after_hours"])
            elif label == "Show Battery":
                screen.pen = rgb(*COLORS["up"]) if settings.get("show_battery", True) else rgb(*COLORS["down"])
            elif label == "Refresh All":
                screen.pen = rgb(*COLORS["neutral"])
            else:
                screen.pen = rgb(*COLORS["text"])
            
            # Right-align value
            val_width = screen.measure_text(value)[0]
            screen.text(value, screen.width - val_width - 6, y_pos)
            
            y_pos += line_height
        
        # Scroll indicators
        if scroll_offset > 0:
            screen.pen = rgb(*COLORS["dim"])
            screen.text("^", screen.width // 2 - 3, menu_top - 4)
        
        if scroll_offset + max_visible < len(menu_items):
            screen.pen = rgb(*COLORS["dim"])
            screen.text("v", screen.width // 2 - 3, menu_bottom + 2)
        
        # Footer
        screen.pen = rgb(*COLORS["dim"])
        footer = "UP/DN:Nav A:Select B:Back"
        screen.text(footer, self.center_x(footer), 110)


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
        
        # Settings
        self.settings = {
            "show_battery": True,
        }
        
        # Settings menu state
        self.settings_index = 0
        self.settings_menu_count = 8  # Total menu items including separator
        
        # Stock data cache
        self.stock_data = {}
        for ticker in STOCKS:
            self.stock_data[ticker] = get_mock_data(ticker)
            self.stock_data[ticker]["last_fetch_ms"] = 0  # Force fetch on startup
        
        # Startup state
        self.startup_index = 0
        self.startup_connecting = True
        
        # Background fetch tracking
        self.last_background_check = 0
        self.background_index = 0
        
        # Refresh indicator
        self.refreshing = False
    
    def current_ticker(self):
        if self.current_index >= len(STOCKS):
            self.current_index = 0
        return STOCKS[self.current_index]
    
    def current_data(self):
        return self.stock_data.get(self.current_ticker(), get_mock_data(self.current_ticker()))
    
    def handle_input(self):
        """Process button input - always responsive."""
        if self.mode == AppMode.STARTUP:
            return  # No input during startup
        
        if self.mode == AppMode.INFO:
            # Settings menu navigation
            if io.BUTTON_UP in io.pressed:
                self.settings_index = (self.settings_index - 1) % self.settings_menu_count
                # Skip separator
                if self.settings_index == 5:
                    self.settings_index = 4
            
            if io.BUTTON_DOWN in io.pressed:
                self.settings_index = (self.settings_index + 1) % self.settings_menu_count
                # Skip separator
                if self.settings_index == 5:
                    self.settings_index = 6
            
            # A button: Toggle selected setting
            if io.BUTTON_A in io.pressed:
                if self.settings_index == 6:  # Battery Icon toggle
                    self.settings["show_battery"] = not self.settings["show_battery"]
                    print(f"[stocks] Battery icon: {self.settings['show_battery']}")
                elif self.settings_index == 7:  # Refresh Now
                    self.force_refresh_all()
            
            # B button: Back to stocks
            if io.BUTTON_B in io.pressed:
                self.mode = AppMode.NORMAL
            return
        
        # Normal mode
        if io.BUTTON_UP in io.pressed:
            self.current_index = (self.current_index - 1) % len(STOCKS)
        
        if io.BUTTON_DOWN in io.pressed:
            self.current_index = (self.current_index + 1) % len(STOCKS)
        
        if io.BUTTON_A in io.pressed:
            self.ticker_size = (self.ticker_size + 1) % TickerSize._COUNT
        
        if io.BUTTON_B in io.pressed:
            self.settings_index = 6  # Start on first toggle option
            self.mode = AppMode.INFO
    
    def force_refresh_all(self):
        """Force refresh all stock data."""
        print("[stocks] Force refresh all...")
        for ticker in STOCKS:
            result = fetch_stock_data(ticker)
            if result:
                self.stock_data[ticker] = result
            else:
                self.stock_data[ticker]["error"] = True
    
    def do_startup(self):
        """Handle startup sequence - fetch all stocks with progress."""
        # First, connect to WiFi
        if self.startup_connecting:
            wifi.tick()
            if wifi.is_connected():
                self.wifi_connected = True
                self.startup_connecting = False
                print("[stocks] WiFi connected")
            elif wifi.connect():
                self.wifi_connected = True
                self.startup_connecting = False
                print("[stocks] WiFi connected")
            else:
                # Keep showing connecting message
                self.display.draw_splash("Connecting WiFi...", 0, len(STOCKS))
                return
        
        # Fetch stocks one at a time
        if self.startup_index < len(STOCKS):
            ticker = STOCKS[self.startup_index]
            self.display.draw_splash(f"Fetching {ticker}...", self.startup_index, len(STOCKS))
            
            # Actually fetch
            result = fetch_stock_data(ticker)
            if result:
                self.stock_data[ticker] = result
            else:
                # Mark error but keep going
                self.stock_data[ticker]["error"] = True
            
            self.startup_index += 1
        else:
            # Done with startup
            print("[stocks] Startup complete")
            self.mode = AppMode.NORMAL
    
    def maybe_refresh_current(self):
        """Check if current stock needs refresh, fetch if so."""
        ticker = self.current_ticker()
        data = self.current_data()
        
        if is_data_fresh(data, self.market_open):
            return  # Data is fresh, no action needed
        
        if is_data_stale(data, self.market_open):
            # Need to refresh
            self.refreshing = True
            result = fetch_stock_data(ticker)
            if result:
                self.stock_data[ticker] = result
            else:
                self.stock_data[ticker]["error"] = True
            self.refreshing = False
    
    def maybe_background_fetch(self):
        """Periodically refresh one non-current stock."""
        now = time.ticks_ms()
        if now - self.last_background_check < BACKGROUND_CHECK_MS:
            return
        
        self.last_background_check = now
        
        # Find a non-current stock that's stale
        current = self.current_ticker()
        for i in range(len(STOCKS)):
            idx = (self.background_index + i) % len(STOCKS)
            ticker = STOCKS[idx]
            if ticker == current:
                continue
            
            data = self.stock_data.get(ticker)
            if is_data_stale(data, self.market_open):
                print(f"[stocks] Background fetch: {ticker}")
                result = fetch_stock_data(ticker)
                if result:
                    self.stock_data[ticker] = result
                else:
                    self.stock_data[ticker]["error"] = True
                self.background_index = (idx + 1) % len(STOCKS)
                break
    
    def update(self):
        """Main update loop."""
        wifi.tick()
        self.handle_input()
        
        # Update market status (cached)
        self.market_open, self.session, self.holiday = fetch_market_status()
        self.wifi_connected = wifi.is_connected()
        
        if self.mode == AppMode.STARTUP:
            self.do_startup()
            return
        
        if self.mode == AppMode.INFO:
            # Find most recent fetch time
            latest = 0
            for data in self.stock_data.values():
                t = data.get("last_fetch_ms", 0)
                if t > latest:
                    latest = t
            self.display.render_settings(
                self.wifi_connected, 
                latest, 
                self.market_open,
                self.settings,
                self.settings_index
            )
            return
        
        # Normal mode
        self.maybe_refresh_current()
        self.maybe_background_fetch()
        
        self.display.render_stock(
            self.current_ticker(),
            self.current_data(),
            self.market_open,
            self.session,
            self.holiday,
            self.ticker_size,
            self.refreshing,
            self.settings
        )


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
    pass

if __name__ == "__main__":
    run(update, init=init, on_exit=on_exit)

