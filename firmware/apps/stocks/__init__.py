# Stocks app for Tufty2350
# Improved version with cleaner code organization and better UX

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

UPDATE_INTERVAL_MS = 10_000  # 10 seconds
WIFI_TIMEOUT_MS = 10_000      # 10 seconds
ANIMATION_PERIOD_MS = 2_000   # Pulse cycle
LIVE_INDICATOR_PERIOD_MS = 1_500  # Faster pulse for live dot

# Colors (defined as tuples for easier manipulation)
COLORS = {
    "up": (0, 255, 0),
    "down": (255, 0, 0),
    "neutral": (200, 200, 200),
    "bg": (0, 0, 0),
    "text": (255, 255, 255),
    "dim": (100, 100, 100),
    "after_hours": (100, 100, 255),
}

# Market hours - now fetched from API, these are fallback only
MARKET_OPEN_HOUR = 9.5   # 9:30 AM EST
MARKET_CLOSE_HOUR = 16.0  # 4:00 PM EST

# Timezone offset for fallback calculation only
try:
    LOCAL_TZ = secrets.TIMEZONE  # e.g., -8 for Pacific
except AttributeError:
    LOCAL_TZ = -8  # Default to Pacific

EST_OFFSET = LOCAL_TZ - (-5)  # Hours to ADD to local time to get EST


# =============================================================================
# Icon Generation (lazy-loaded)
# =============================================================================

ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAyElEQVR42u2YQQrAMAwDNZWDHkT8h"
    "/0fpx7Eg4cRPIoH8SAe5iDeRPygHsSDhJF4EA/iQTyIB/EgXsSDeBAPwgH+EzG3KMzd2Ww2m81m"
    "M/PnP2+z2Ww2m80YY9M0lSQBUFVV13UlSYIxZls2bZskSQpBwHVdXdedd56WJWmaJkmSJEmSJEmS"
    "JEmSJEmSJEmSJEmSJEmSJP+GZLP5j9lsNv+p6xrHcRzHcRzHcRzHcRzHcRzHcRyHMQZjDMYYjDEY"
    "YzDGAAwDAAz/hf8fKxRWAStU5hsqFFYBK1TmGyoUVgErVOYbKhRWAStU5hsqFFYBK1TmGyoUVgEr"
    "VOYbKhRWAStU5g8qFFYBK1TmDyoUVgErVOYPKhRWAStU5g8qFFYBK1TmDyoUVgErVOYPKhRWAStU"
    "5g8qFFYBK1TmHyoUVgErVOY3VCisAlatDXQAAAAASUVORK5CYII="
)

def _ensure_icon():
    """Generate icon file if missing."""
    icon_path = f"{APP_DIR}/icon.png"
    try:
        with open(icon_path, "rb"):
            return
    except OSError:
        pass
    
    try:
        import base64
        with open(icon_path, "wb") as f:
            f.write(base64.b64decode(ICON_B64))
    except Exception:
        pass

_ensure_icon()


# =============================================================================
# Load Configuration from secrets.py
# =============================================================================

def _load_config():
    """Load stocks list and API key from secrets."""
    try:
        stock_list = secrets.STOCKS
    except AttributeError:
        stock_list = ["TSLA", "PLTR", "SPY", "QQQ"]
    
    try:
        api_key = secrets.FINNHUB_KEY
        print("[stocks] Finnhub key loaded OK")
    except AttributeError:
        api_key = None
        print("[stocks] WARNING: no FINNHUB_KEY in secrets.py — will use mock data")
    
    return stock_list, api_key

STOCKS, FINNHUB_KEY = _load_config()


# =============================================================================
# Mock Data (fallback when offline or no API key)
# =============================================================================

MOCK_DATA = {
    "TSLA": {"price": 420.00, "change": 5.25, "change_percent": 1.26},
    "PLTR": {"price": 35.50, "change": 0.75, "change_percent": 2.15},
    "SPY":  {"price": 385.20, "change": -2.10, "change_percent": -0.54},
    "QQQ":  {"price": 315.75, "change": 3.45, "change_percent": 1.10},
}

def get_mock_data(ticker):
    """Return mock data for a ticker, with sensible default."""
    return MOCK_DATA.get(ticker, MOCK_DATA["TSLA"]).copy()


# =============================================================================
# State Machine
# =============================================================================

class AppState:
    RUNNING = 0
    CONNECTING = 1
    CONNECTED = 2
    FETCHING = 3


class ViewMode:
    STOCKS = 0
    INFO = 1


# =============================================================================
# Formatting Utilities (DRY)
# =============================================================================

def _fmt_decimal(val, decimals=2):
    """Format a number with fixed decimal places."""
    rounded = round(val, decimals)
    s = str(rounded)
    if "." not in s:
        return s + "." + "0" * decimals
    integer, frac = s.split(".")
    # Pad with zeros (ljust not available in MicroPython)
    while len(frac) < decimals:
        frac += "0"
    return integer + "." + frac


def fmt_price(val):
    """Format as currency: $123.45"""
    return "$" + _fmt_decimal(val, 2)


def fmt_change(val):
    """Format change with sign: +1.23 or -1.23"""
    prefix = "+" if val >= 0 else ""
    return prefix + _fmt_decimal(val, 2)


def fmt_percent(val):
    """Format percentage with sign: +1.23% or -1.23%"""
    return fmt_change(val) + "%"


def fmt_time_ago(ms_ago):
    """Format milliseconds ago as readable string."""
    if ms_ago < 0:
        return "Never"
    secs = ms_ago // 1000
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    return f"{secs // 3600}h ago"


# =============================================================================
# Market Hours Utilities
# =============================================================================

def is_market_open_fallback():
    """Fallback: Check market hours using local time calculation."""
    try:
        now = time.localtime()
        weekday = now[6]  # 0=Monday, 6=Sunday
        hour = now[3]
        minute = now[4]
        
        # Convert local time to EST
        est_hour = hour - EST_OFFSET
        est_weekday = weekday
        
        # Handle day rollover
        if est_hour >= 24:
            est_hour -= 24
            est_weekday = (weekday + 1) % 7
        elif est_hour < 0:
            est_hour += 24
            est_weekday = (weekday - 1) % 7
        
        # Weekend check (in EST)
        if est_weekday > 4:
            return False, None, None
        
        current_time = est_hour + minute / 60.0
        is_open = MARKET_OPEN_HOUR <= current_time < MARKET_CLOSE_HOUR
        session = "regular" if is_open else None
        return is_open, session, None
    except Exception:
        return True, None, None  # Assume open on error


# Cache for market status (avoid hammering API)
_market_status_cache = {
    "is_open": None,
    "session": None,
    "holiday": None,
    "last_fetch": 0,
}
MARKET_STATUS_CACHE_MS = 60_000  # Cache for 1 minute


def fetch_market_status():
    """Fetch market status from Finnhub API."""
    global _market_status_cache
    
    now = time.ticks_ms()
    
    # Return cached if fresh
    if _market_status_cache["is_open"] is not None:
        if now - _market_status_cache["last_fetch"] < MARKET_STATUS_CACHE_MS:
            return (
                _market_status_cache["is_open"],
                _market_status_cache["session"],
                _market_status_cache["holiday"],
            )
    
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
        session = data.get("session")  # pre-market, regular, post-market, or None
        holiday = data.get("holiday")  # Holiday name or None
        
        # Update cache
        _market_status_cache["is_open"] = is_open
        _market_status_cache["session"] = session
        _market_status_cache["holiday"] = holiday
        _market_status_cache["last_fetch"] = now
        
        print(f"[stocks] Market status: open={is_open}, session={session}, holiday={holiday}")
        return is_open, session, holiday
        
    except Exception as e:
        print(f"[stocks] Market status error: {e}")
        return is_market_open_fallback()


def is_market_open():
    """Check if market is open (uses cached API result)."""
    is_open, _, _ = fetch_market_status()
    return is_open


def get_market_session():
    """Get current market session (pre-market, regular, post-market, or None)."""
    _, session, _ = fetch_market_status()
    return session


def get_market_holiday():
    """Get holiday name if market is closed for holiday."""
    _, _, holiday = fetch_market_status()
    return holiday


# =============================================================================
# System Info Utilities
# =============================================================================

def get_battery_percent():
    """Read battery percentage. Returns None if not available."""
    try:
        # Tufty 2350 battery reading via ADC
        from machine import ADC
        vbat_adc = ADC(29)  # Battery voltage on GPIO29
        vref_adc = ADC(28)  # Reference voltage on GPIO28
        
        # Read values
        vref = vref_adc.read_u16()
        vbat = vbat_adc.read_u16()
        
        if vref == 0:
            return None
        
        # Calculate voltage (3.3V reference, voltage divider)
        voltage = (vbat / vref) * 3.3 * 2
        
        # Estimate percentage (3.0V = 0%, 4.2V = 100%)
        percent = (voltage - 3.0) / (4.2 - 3.0) * 100
        return max(0, min(100, int(percent)))
    except Exception:
        return None


def get_wifi_ssid():
    """Get connected WiFi SSID."""
    try:
        if wifi.is_connected():
            # Try to get SSID from secrets
            return getattr(secrets, "WIFI_SSID", "Connected")
        return "Not connected"
    except Exception:
        return "Unknown"


def get_ip_address():
    """Get current IP address."""
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            return wlan.ifconfig()[0]
        return "N/A"
    except Exception:
        return "N/A"

def get_pulse_alpha(current_ms, period=ANIMATION_PERIOD_MS):
    """Get alpha value (0.5-1.0) for smooth pulsing animation."""
    phase = (current_ms % period) / period
    return 0.5 + easeOutSine(phase) * 0.5


def blend_color(base_rgb, alpha):
    """Apply alpha to an RGB tuple."""
    return tuple(int(c * alpha) for c in base_rgb)


def rgb(r, g, b):
    """Convert RGB tuple to color value."""
    return color.rgb(r, g, b)


# =============================================================================
# Data Fetching
# =============================================================================

def fetch_stock_data(ticker):
    """Fetch stock data from Finnhub API. Falls back to mock on failure."""
    if FINNHUB_KEY is None:
        print(f"[stocks] No API key, using mock for {ticker}")
        return get_mock_data(ticker)
    
    print(f"[stocks] Fetching {ticker} from Finnhub...")
    try:
        import urequests
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}"
        resp = urequests.get(url, timeout=10)
        
        if resp.status_code != 200:
            print(f"[stocks] HTTP {resp.status_code} for {ticker}")
            resp.close()
            return get_mock_data(ticker)
        
        data = json.loads(resp.text)
        resp.close()
        
        # Finnhub returns c=0 when no data available
        if data.get("c", 0) == 0:
            print(f"[stocks] No data for {ticker}, using mock")
            return get_mock_data(ticker)
        
        result = {
            "price": data["c"],
            "change": data.get("d", 0) or 0,
            "change_percent": data.get("dp", 0) or 0,
        }
        print(f"[stocks] {ticker}: ${result['price']:.2f} ({result['change']:+.2f})")
        return result
        
    except ImportError as e:
        print(f"[stocks] ImportError: {e}")
    except Exception as e:
        print(f"[stocks] Error fetching {ticker}: {e}")
    
    return get_mock_data(ticker)


def fetch_all_stocks(app_state):
    """Fetch data for all configured stocks."""
    print("[stocks] Fetching all stocks...")
    for i, ticker in enumerate(STOCKS):
        user_message("Fetching Data", [f"Fetching {ticker}...", f"{i + 1}/{len(STOCKS)}"])
        try:
            app_state["stock_data"][ticker] = fetch_stock_data(ticker)
        except Exception as e:
            print(f"[stocks] Error: {e}")
            app_state["stock_data"][ticker] = get_mock_data(ticker)
    
    app_state["last_update"] = time.ticks_ms()
    State.save("stocks", app_state)
    print("[stocks] Fetch complete")


# =============================================================================
# Display Rendering
# =============================================================================

class StockDisplay:
    """Handles all screen rendering for the stocks app."""
    
    def __init__(self):
        self.large_font = pixel_font.load("/system/assets/fonts/smart.ppf")
        self.small_font = pixel_font.load("/system/assets/fonts/fear.ppf")
        screen.antialias = image.X4
    
    def center_x(self, text):
        """Calculate X position to center text."""
        return (screen.width - screen.measure_text(text)[0]) // 2
    
    def draw_background(self, market_open, change, current_ms):
        """Draw background with optional pulse during market hours."""
        if not market_open:
            screen.pen = rgb(*COLORS["bg"])
        else:
            alpha = get_pulse_alpha(current_ms)
            if change > 0:
                base = (30, 60, 30)  # Dim green
            elif change < 0:
                base = (60, 30, 30)  # Dim red
            else:
                base = (40, 40, 40)  # Neutral
            screen.pen = rgb(*blend_color(base, alpha))
        screen.clear()
    
    def draw_status_indicators(self, market_open, wifi_connected, current_ms):
        """Draw WiFi and market status indicators in corners."""
        screen.font = self.small_font
        
        # Top-left: Live indicator
        if market_open:
            alpha = get_pulse_alpha(current_ms, LIVE_INDICATOR_PERIOD_MS)
            screen.pen = rgb(*blend_color(COLORS["up"], alpha))
            screen.text("*", 8, 6)
        else:
            screen.pen = rgb(*COLORS["dim"])
            screen.text(".", 8, 6)
        
        # Top-right: WiFi indicator
        if wifi_connected:
            screen.pen = rgb(*COLORS["up"])
            screen.text("W", screen.width - 16, 6)
        else:
            screen.pen = rgb(*COLORS["dim"])
            screen.text("-", screen.width - 16, 6)
    
    def draw_ticker(self, ticker):
        """Draw the stock ticker symbol."""
        screen.font = self.large_font
        screen.pen = rgb(*COLORS["text"])
        screen.text(ticker, self.center_x(ticker), 10)
    
    def draw_price(self, price, market_open, current_ms):
        """Draw the current price with optional after-hours pulse."""
        screen.font = self.large_font
        price_str = fmt_price(price)
        
        if market_open:
            screen.pen = rgb(*COLORS["text"])
        else:
            alpha = get_pulse_alpha(current_ms)
            screen.pen = rgb(*blend_color(COLORS["text"], alpha))
        
        screen.text(price_str, self.center_x(price_str), 34)
    
    def draw_change(self, change, change_percent):
        """Draw price change with directional coloring."""
        screen.font = self.small_font
        
        if change > 0:
            direction, col = "UP", COLORS["up"]
        elif change < 0:
            direction, col = "DN", COLORS["down"]
        else:
            direction, col = "--", COLORS["neutral"]
        
        change_str = f"{direction} {fmt_change(change)} ({fmt_percent(change_percent)})"
        screen.pen = rgb(*col)
        screen.text(change_str, self.center_x(change_str), 56)
    
    def draw_market_status(self, market_open, session, holiday):
        """Draw market open/closed status with session info."""
        screen.font = self.small_font
        
        if holiday:
            # Show holiday name
            status = holiday
            screen.pen = rgb(*COLORS["after_hours"])
        elif market_open:
            if session == "pre-market":
                status = "Pre-Market"
                screen.pen = rgb(*COLORS["neutral"])
            elif session == "post-market":
                status = "After Hours"
                screen.pen = rgb(*COLORS["after_hours"])
            else:  # regular
                status = "Market OPEN"
                screen.pen = rgb(*COLORS["up"])
        else:
            status = "Market CLOSED"
            screen.pen = rgb(*COLORS["after_hours"])
        
        screen.text(status, self.center_x(status), 72)
    
    def render(self, ticker, data, market_open, session, holiday, wifi_connected):
        """Render the complete stock display."""
        current_ms = time.ticks_ms()
        change = data.get("change", 0)
        
        self.draw_background(market_open, change, current_ms)
        self.draw_status_indicators(market_open, wifi_connected, current_ms)
        self.draw_ticker(ticker)
        self.draw_price(data.get("price", 0), market_open, current_ms)
        self.draw_change(change, data.get("change_percent", 0))
        self.draw_market_status(market_open, session, holiday)
    
    def render_info(self, wifi_connected, last_update, market_open):
        """Render the info/status screen."""
        current_ms = time.ticks_ms()
        
        # Dark background
        screen.pen = rgb(*COLORS["bg"])
        screen.clear()
        
        # Title
        screen.font = self.large_font
        screen.pen = rgb(*COLORS["text"])
        title = "System Info"
        screen.text(title, self.center_x(title), 6)
        
        # Info lines
        screen.font = self.small_font
        y_pos = 28
        line_height = 14
        
        # WiFi Status
        if wifi_connected:
            ssid = get_wifi_ssid()
            screen.pen = rgb(*COLORS["up"])
            screen.text(f"WiFi: {ssid}", 8, y_pos)
        else:
            screen.pen = rgb(*COLORS["down"])
            screen.text("WiFi: Disconnected", 8, y_pos)
        y_pos += line_height
        
        # IP Address
        screen.pen = rgb(*COLORS["dim"])
        ip = get_ip_address()
        screen.text(f"IP: {ip}", 8, y_pos)
        y_pos += line_height
        
        # Last Update
        ms_ago = time.ticks_ms() - last_update
        screen.pen = rgb(*COLORS["dim"])
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
        
        # Market Status
        if market_open:
            screen.pen = rgb(*COLORS["up"])
            screen.text("Market: OPEN", 8, y_pos)
        else:
            screen.pen = rgb(*COLORS["after_hours"])
            screen.text("Market: CLOSED", 8, y_pos)
        y_pos += line_height
        
        # Stock count
        screen.pen = rgb(*COLORS["dim"])
        screen.text(f"Tracking: {len(STOCKS)} stocks", 8, y_pos)
        
        # Footer hint
        screen.pen = rgb(*COLORS["dim"])
        hint = "Press B to return"
        screen.text(hint, self.center_x(hint), 108)


# =============================================================================
# App Controller
# =============================================================================

class StocksApp:
    """Main application controller."""
    
    def __init__(self):
        self.display = StockDisplay()
        self.state = AppState.CONNECTING
        self.view_mode = ViewMode.STOCKS
        self.wifi_start_time = time.ticks_ms()
        
        # Persistent state
        self.data = {
            "current_stock_index": 0,
            "stock_data": {},
            "last_update": -400000,
            "wifi_connected": False,
            "market_open": True,
        }
        State.load("stocks", self.data)
        
        # Ensure all stocks have data
        for ticker in STOCKS:
            if ticker not in self.data["stock_data"]:
                self.data["stock_data"][ticker] = get_mock_data(ticker)
    
    def get_current_stock(self):
        """Get current ticker and its data, with bounds checking."""
        idx = self.data["current_stock_index"]
        if idx >= len(STOCKS):
            idx = self.data["current_stock_index"] = 0
        
        ticker = STOCKS[idx]
        if ticker not in self.data["stock_data"]:
            self.data["stock_data"][ticker] = get_mock_data(ticker)
        
        return ticker, self.data["stock_data"][ticker]
    
    def navigate_stocks(self, delta):
        """Navigate to previous/next stock."""
        self.data["current_stock_index"] = (
            self.data["current_stock_index"] + delta
        ) % len(STOCKS)
        State.save("stocks", self.data)
    
    def handle_input(self):
        """Process button input."""
        # Navigation: Up = previous, Down = next (only in stocks view)
        if self.view_mode == ViewMode.STOCKS:
            if io.BUTTON_UP in io.pressed:
                self.navigate_stocks(-1)
            if io.BUTTON_DOWN in io.pressed:
                self.navigate_stocks(1)
        
        # B button: Toggle info screen (or return from info)
        if io.BUTTON_B in io.pressed:
            if self.view_mode == ViewMode.INFO:
                # Return to stocks view
                self.view_mode = ViewMode.STOCKS
            elif self.state == AppState.RUNNING:
                # Show info screen
                self.view_mode = ViewMode.INFO
        
        # A and C buttons reserved for future use
        # if io.BUTTON_A in io.pressed:
        #     pass
        # if io.BUTTON_C in io.pressed:
        #     pass
    
    def update_state_machine(self):
        """Process state machine transitions."""
        now = time.ticks_ms()
        
        if self.state == AppState.RUNNING:
            # Check for auto-update
            if now - self.data["last_update"] >= UPDATE_INTERVAL_MS:
                print("[stocks] Auto-update interval reached")
                user_message("Stocks Update", ["Connecting to", "WiFi..."])
                self.state = AppState.CONNECTING
                self.wifi_start_time = now
            else:
                self.data["wifi_connected"] = wifi.is_connected()
        
        elif self.state == AppState.CONNECTING:
            elapsed = now - self.wifi_start_time
            user_message("Connecting", ["WiFi...", f"{elapsed // 1000}s..."])
            
            if wifi.is_connected() or wifi.connect():
                print("[stocks] WiFi connected")
                self.state = AppState.CONNECTED
                self.data["wifi_connected"] = True
            elif elapsed >= WIFI_TIMEOUT_MS:
                print("[stocks] WiFi timeout")
                user_message("Connection Failed", ["Using cached", "data..."])
                self.state = AppState.RUNNING
                self.data["wifi_connected"] = False
        
        elif self.state == AppState.CONNECTED:
            user_message("WiFi Connected", ["Fetching stock", "prices..."])
            self.state = AppState.FETCHING
        
        elif self.state == AppState.FETCHING:
            fetch_all_stocks(self.data)
            user_message("Update Complete", ["Stock data", "refreshed!"])
            self.state = AppState.RUNNING
            self.data["wifi_connected"] = True
    
    def update(self):
        """Main update loop - called every frame."""
        wifi.tick()
        self.handle_input()
        self.update_state_machine()
        
        # Update market status from API (cached)
        market_open, session, holiday = fetch_market_status()
        self.data["market_open"] = market_open
        
        # Render appropriate view
        if self.view_mode == ViewMode.INFO:
            self.display.render_info(
                wifi_connected=self.data["wifi_connected"],
                last_update=self.data["last_update"],
                market_open=self.data["market_open"],
            )
        else:
            ticker, data = self.get_current_stock()
            self.display.render(
                ticker=ticker,
                data=data,
                market_open=market_open,
                session=session,
                holiday=holiday,
                wifi_connected=self.data["wifi_connected"],
            )


# =============================================================================
# Entry Points
# =============================================================================

_app = None

def init():
    global _app
    _app = StocksApp()
    State.save("stocks", _app.data)


def update():
    _app.update()


def on_exit():
    pass


# Standalone support for Thonny debugging
if __name__ == "__main__":
    run(update, init=init, on_exit=on_exit)

