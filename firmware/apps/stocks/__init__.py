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

from badgeware import run, State
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

def get_battery_percent():
    try:
        from machine import ADC
        vbat_adc = ADC(29)
        vref_adc = ADC(28)
        vref = vref_adc.read_u16()
        vbat = vbat_adc.read_u16()
        if vref == 0:
            return None
        voltage = (vbat / vref) * 3.3 * 2
        percent = (voltage - 3.0) / (4.2 - 3.0) * 100
        return max(0, min(100, int(percent)))
    except Exception:
        return None

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
        self.font_medium = pixel_font.load("/system/assets/fonts/futile.ppf")
        self.font_large = pixel_font.load("/system/assets/fonts/ignore.ppf")
        screen.antialias = image.X4
    
    def center_x(self, text):
        w = screen.measure_text(text)[0]
        return (screen.width - w) // 2
    
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
    
    def render_stock(self, ticker, data, market_open, session, holiday, ticker_size, refreshing=False):
        """Render main stock display."""
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
    
    def render_info(self, wifi_connected, last_update, market_open):
        """Render system info screen."""
        screen.pen = rgb(*COLORS["bg"])
        screen.clear()
        
        screen.font = self.font_medium
        screen.pen = rgb(*COLORS["text"])
        title = "System Info"
        screen.text(title, self.center_x(title), 6)
        
        screen.font = self.font_small
        y_pos = 28
        line_height = 14
        
        # WiFi
        if wifi_connected:
            screen.pen = rgb(*COLORS["up"])
            screen.text(f"WiFi: {get_wifi_ssid()}", 8, y_pos)
        else:
            screen.pen = rgb(*COLORS["down"])
            screen.text("WiFi: Disconnected", 8, y_pos)
        y_pos += line_height
        
        # IP
        screen.pen = rgb(*COLORS["dim"])
        screen.text(f"IP: {get_ip_address()}", 8, y_pos)
        y_pos += line_height
        
        # Last update
        ms_ago = time.ticks_ms() - last_update
        screen.text(f"Updated: {fmt_time_ago(ms_ago)}", 8, y_pos)
        y_pos += line_height
        
        # Battery
        battery = get_battery_percent()
        if battery is not None:
            if battery > 50:
                screen.pen = rgb(*COLORS["up"])
            elif battery > 20:
                screen.pen = rgb(*COLORS["neutral"])
            else:
                screen.pen = rgb(*COLORS["down"])
            screen.text(f"Battery: {battery}%", 8, y_pos)
        else:
            screen.pen = rgb(*COLORS["dim"])
            screen.text("Battery: N/A", 8, y_pos)
        y_pos += line_height
        
        # Market
        if market_open:
            screen.pen = rgb(*COLORS["up"])
            screen.text("Market: OPEN", 8, y_pos)
        else:
            screen.pen = rgb(*COLORS["after_hours"])
            screen.text("Market: CLOSED", 8, y_pos)
        y_pos += line_height
        
        # Stocks
        screen.pen = rgb(*COLORS["dim"])
        screen.text(f"Tracking: {len(STOCKS)} stocks", 8, y_pos)
        
        # Footer
        screen.text("Press B to return", self.center_x("Press B to return"), 108)


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
            self.mode = AppMode.INFO
    
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
            self.display.render_info(self.wifi_connected, latest, self.market_open)
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
            self.refreshing
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

