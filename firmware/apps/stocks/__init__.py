# Stocks app for Tufty2350
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

# Generate icon if it doesn't exist
icon_path = f"{APP_DIR}/icon.png"
try:
    with open(icon_path, "rb"):
        pass
except OSError:
    import base64
    icon_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAyElEQVR42u2YQQrAMAwDNZWDHkT8h/0fpx7Eg4cRPIoH8SAe5iDeRPygHsSDhJF4EA/iQTyIB/EgXsSDeBAPwgH+EzG3KMzd2Ww2m81mM/PnP2+z2Ww2m80YY9M0lSQBUFVV13UlSYIxZls2bZskSQpBwHVdXdedd56WJWmaJkmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJP+GZLP5j9lsNv+p6xrHcRzHcRzHcRzHcRzHcRzHcRyHMQZjDMYYjDEYYzDGAAwDAAz/hf8fKxRWAStU5hsqFFYBK1TmGyoUVgErVOYbKhRWAStU5hsqFFYBK1TmGyoUVgErVOYbKhRWAStU5g8qFFYBK1TmDyoUVgErVOYPKhRWAStU5g8qFFYBK1TmDyoUVgErVOYPKhRWAStU5g8qFFYBK1TmHyoUVgErVOY3VCisAlatDXQAAAAASUVORK5CYII="
    )
    try:
        with open(icon_path, "wb") as f:
            f.write(icon_data)
    except Exception:
        pass

# Import stocks list and API key from secrets
try:
    stocks = secrets.STOCKS
except AttributeError:
    stocks = ["TSLA", "PLTR", "SPY", "QQQ"]

try:
    FINNHUB_KEY = secrets.FINNHUB_KEY
    print("[stocks] Finnhub key loaded OK")
except AttributeError:
    FINNHUB_KEY = None
    print("[stocks] WARNING: no FINNHUB_KEY in secrets.py — will use mock data")

# State machine
class StocksState:
    Running = 0
    ConnectWiFi = 1
    WiFiConnected = 2
    FetchData = 3

# App state
state = {
    "current_stock_index": 0,
    "stock_data": {},
    "last_update": -400000,
    "wifi_connected": False,
    "market_open": True,
}

State.load("stocks", state)

stocks_state = StocksState.ConnectWiFi
last_data_fetch_attempt = time.ticks_ms()
wifi_connect_started = time.ticks_ms()
animation_start_time = time.ticks_ms()  # For pulsing animation

UPDATE_INTERVAL = 300000   # 5 minutes in ms
WIFI_TIMEOUT = 10000       # 10 seconds before giving up on wifi
ANIMATION_PERIOD = 2000    # 2 seconds for pulsing animation

# Colors
COLOR_UP = color.rgb(0, 255, 0)
COLOR_DOWN = color.rgb(255, 0, 0)
COLOR_NEUTRAL = color.rgb(200, 200, 200)
COLOR_BG = color.rgb(0, 0, 0)
COLOR_TEXT = color.rgb(255, 255, 255)
COLOR_DIM = color.rgb(100, 100, 100)
COLOR_AFTER_HOURS = color.rgb(100, 100, 255)

# Fonts
large_font = pixel_font.load("/system/assets/fonts/smart.ppf")
small_font = pixel_font.load("/system/assets/fonts/fear.ppf")

screen.antialias = image.X4

# Mock stock data for fallback
MOCK_STOCK_DATA = {
    "TSLA": {"price": 420.00, "change": 5.25, "change_percent": 1.26},
    "PLTR": {"price": 35.50, "change": 0.75, "change_percent": 2.15},
    "SPY": {"price": 385.20, "change": -2.10, "change_percent": -0.54},
    "QQQ": {"price": 315.75, "change": 3.45, "change_percent": 1.10},
}


def fmt_price(val):
    rounded = round(val, 2)
    s = str(rounded)
    if "." not in s:
        s = s + ".00"
    else:
        parts = s.split(".")
        if len(parts[1]) == 1:
            s = s + "0"
    return "$" + s


def fmt_change(val):
    rounded = round(val, 2)
    s = str(rounded)
    if "." not in s:
        s = s + ".00"
    else:
        parts = s.split(".")
        if len(parts[1]) == 1:
            s = s + "0"
    if rounded >= 0:
        return "+" + s
    return s


def fmt_percent(val):
    rounded = round(val, 2)
    s = str(rounded)
    if "." not in s:
        s = s + ".00"
    else:
        parts = s.split(".")
        if len(parts[1]) == 1:
            s = s + "0"
    if rounded >= 0:
        return "+" + s + "%"
    return s + "%"


def center_x(text_str):
    w = screen.measure_text(text_str)[0]
    return (screen.width - w) // 2


def is_market_open():
    """Check if US stock market (EST/EDT) is currently open.
    Market open: 9:30 AM - 4:00 PM EST/EDT, Mon-Fri only."""
    try:
        import time as time_module
        now = time_module.localtime()
        
        # Get weekday (0=Monday, 6=Sunday)
        weekday = now[6]
        hour = now[3]
        minute = now[4]
        
        # Only open Mon-Fri (weekday 0-4)
        if weekday > 4:  # Weekend
            return False
        
        # Market hours: 9:30 AM (9.5) to 4:00 PM (16:00)
        # Note: This assumes system time is in EST/EDT
        current_hour_min = hour + minute / 60.0
        return 9.5 <= current_hour_min < 16.0
    except Exception:
        return True  # Assume open on error


def seconds_until_market_open():
    """Calculate seconds until next market open (9:30 AM EST, next Mon-Fri)."""
    try:
        import time as time_module
        now = time_module.localtime()
        
        weekday = now[6]  # 0=Monday, 6=Sunday
        hour = now[3]
        minute = now[4]
        second = now[5]
        
        current_seconds = hour * 3600 + minute * 60 + second
        market_open_seconds = 9.5 * 3600  # 9:30 AM = 34200 seconds
        
        # If before market open today and it's a weekday (Mon-Fri)
        if weekday < 5 and current_seconds < market_open_seconds:
            return market_open_seconds - current_seconds
        
        # If it's a weekday (Mon-Fri) after market hours, next open is tomorrow morning
        if weekday < 5:
            seconds_until_midnight = 86400 - current_seconds
            return seconds_until_midnight + market_open_seconds
        
        # It's the weekend (Sat=5, Sun=6)
        # Next market open is Monday 9:30 AM
        days_until_monday = 7 - weekday  # Sat: 2 days, Sun: 1 day
        seconds_until_midnight = 86400 - current_seconds
        return seconds_until_midnight + (days_until_monday - 1) * 86400 + market_open_seconds
    except Exception:
        return 0


def format_countdown(seconds):
    """Format seconds as 'Xh Ym' countdown."""
    if seconds < 0:
        seconds = 0
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    if hours > 0:
        return str(hours) + "h " + str(minutes) + "m"
    else:
        return str(minutes) + "m"


def format_last_update(ms_ago):
    """Format milliseconds ago as readable string."""
    if ms_ago < 0:
        return "Never"
    
    seconds_ago = ms_ago // 1000
    
    if seconds_ago < 60:
        return str(seconds_ago) + "s ago"
    elif seconds_ago < 3600:
        minutes = seconds_ago // 60
        return str(minutes) + "m ago"
    else:
        hours = seconds_ago // 3600
        return str(hours) + "h ago"


def get_pulse_alpha(current_ms, animation_period=ANIMATION_PERIOD):
    """Get alpha value (0-1) for pulsing animation using easing function."""
    phase = (current_ms % animation_period) / animation_period
    # easeOutSine creates smooth pulse: 1.0 -> 0.5 -> 1.0
    pulse = easeOutSine(phase)
    return 0.5 + (pulse * 0.5)  # Range from 0.5 to 1.0


def get_background_color(market_open, change, current_ms):
    """Get background color based on market status and price direction.
    During market hours: subtle pulse between black and dim green/red.
    After hours: static black."""
    if not market_open:
        return COLOR_BG
    
    # During market hours, pulse the background based on price direction
    alpha = get_pulse_alpha(current_ms)
    
    if change > 0:
        # Dim green pulse: from black to subtle green
        r = int(30 * alpha)
        g = int(60 * alpha)
        b = int(30 * alpha)
    elif change < 0:
        # Dim red pulse: from black to subtle red
        r = int(60 * alpha)
        g = int(30 * alpha)
        b = int(30 * alpha)
    else:
        # Neutral gray pulse
        r = int(40 * alpha)
        g = int(40 * alpha)
        b = int(40 * alpha)
    
    return color.rgb(r, g, b)


def fetch_stock_data(ticker):
    """Fetch stock data from Finnhub. Falls back to mock on any failure."""
    if FINNHUB_KEY is None:
        print("[stocks] no API key, returning mock for " + ticker)
        return MOCK_STOCK_DATA.get(ticker, MOCK_STOCK_DATA["TSLA"])

    print("[stocks] fetching " + ticker + " from Finnhub...")
    try:
        import urequests
        url = "https://finnhub.io/api/v1/quote?symbol=" + ticker + "&token=" + FINNHUB_KEY
        print("[stocks] GET " + url)
        r = urequests.get(url, timeout=10)
        print("[stocks] status=" + str(r.status_code))
        raw = r.text
        print("[stocks] response: " + raw[:200])
        data = json.loads(raw)
        r.close()

        # Finnhub returns c=0 when market is closed and no data available
        current_price = data["c"]
        if current_price == 0:
            print("[stocks] Finnhub returned c=0 for " + ticker + ", using mock")
            return MOCK_STOCK_DATA.get(ticker, MOCK_STOCK_DATA["TSLA"])

        change = data["d"]          # dollar change
        change_percent = data["dp"] # percent change

        print("[stocks] OK " + ticker + " price=" + str(current_price) + " change=" + str(change))
        return {
            "price": current_price,
            "change": change,
            "change_percent": change_percent,
        }
    except ImportError as e:
        print("[stocks] ImportError: " + str(e))
    except Exception as e:
        print("[stocks] Exception: " + str(e))

    print("[stocks] falling back to mock data for " + ticker)
    return MOCK_STOCK_DATA.get(ticker, MOCK_STOCK_DATA["TSLA"])


def fetch_all_stocks():
    """Fetch data for all stocks in the list."""
    print("[stocks] fetch_all_stocks() called")
    for i, ticker in enumerate(stocks):
        progress = str(i + 1) + "/" + str(len(stocks))
        user_message("Fetching Data", ["Fetching " + ticker + "...", progress])

        try:
            state["stock_data"][ticker] = fetch_stock_data(ticker)
        except Exception as e:
            print("[stocks] outer exception for " + ticker + ": " + str(e))
            state["stock_data"][ticker] = MOCK_STOCK_DATA.get(ticker, MOCK_STOCK_DATA["TSLA"])

    state["last_update"] = time.ticks_ms()
    State.save("stocks", state)
    print("[stocks] fetch_all_stocks() done")


def get_current_stock():
    if state["current_stock_index"] >= len(stocks):
        state["current_stock_index"] = 0

    ticker = stocks[state["current_stock_index"]]

    if ticker not in state["stock_data"]:
        state["stock_data"][ticker] = MOCK_STOCK_DATA.get(ticker, MOCK_STOCK_DATA["TSLA"])

    return ticker, state["stock_data"][ticker]


def draw_stock_display():
    """Draw the main stock display with after-hours enhancements."""
    current_ms = time.ticks_ms()
    
    ticker, data = get_current_stock()

    price = data.get("price", 0)
    change = data.get("change", 0)
    change_percent = data.get("change_percent", 0)

    if change > 0:
        change_color = COLOR_UP
        direction = "UP"
    elif change < 0:
        change_color = COLOR_DOWN
        direction = "DN"
    else:
        change_color = COLOR_NEUTRAL
        direction = "--"

    # Check if market is open
    market_open = is_market_open()
    state["market_open"] = market_open

    # --- Background: subtle pulse during market hours ---
    bg_color = get_background_color(market_open, change, current_ms)
    screen.pen = bg_color
    screen.clear()

    # --- Top-left corner: Live data indicator (pulses green during market hours) ---
    screen.font = small_font
    if market_open:
        live_alpha = get_pulse_alpha(current_ms, 1500)  # Faster pulse (1.5s)
        r = int(0 * live_alpha)
        g = int(255 * live_alpha)
        b = int(0 * live_alpha)
        screen.pen = color.rgb(r, g, b)
        screen.text("●", 8, 6)
    else:
        screen.pen = COLOR_DIM
        screen.text("○", 8, 6)

    # --- Top-right corner: WiFi indicator ---
    if state["wifi_connected"]:
        screen.pen = COLOR_UP  # Green when connected
        screen.text("⚡", screen.width - 16, 6)
    else:
        screen.pen = COLOR_DIM  # Gray when offline
        screen.text("⚠", screen.width - 16, 6)

    # --- Ticker symbol (y=10) ---
    screen.font = large_font
    screen.pen = COLOR_TEXT
    ticker_label = ticker
    screen.text(ticker_label, center_x(ticker_label), 10)

    # --- Price (y=34) with after-hours pulsing animation ---
    screen.font = large_font
    price_str = fmt_price(price)
    
    if not market_open:
        # Apply subtle pulsing effect during after-hours
        alpha = get_pulse_alpha(current_ms)
        # Fade price between full brightness and dim
        r = int(255 * alpha)
        g = int(255 * alpha)
        b = int(255 * alpha)
        screen.pen = color.rgb(r, g, b)
    else:
        screen.pen = COLOR_TEXT
    
    screen.text(price_str, center_x(price_str), 34)

    # --- Change line (y=56) ---
    screen.font = small_font
    change_str = direction + " " + fmt_change(change) + " (" + fmt_percent(change_percent) + ")"
    screen.pen = change_color
    screen.text(change_str, center_x(change_str), 56)

    # --- Market status and countdown (y=72) ---
    screen.font = small_font
    if market_open:
        status_str = "Market OPEN"
        screen.pen = COLOR_UP
    else:
        status_str = "Market CLOSED"
        screen.pen = COLOR_AFTER_HOURS
    
    screen.text(status_str, center_x(status_str), 72)

    # --- Countdown to market open (y=85) ---
    screen.font = small_font
    screen.pen = COLOR_DIM
    
    if not market_open:
        countdown_seconds = seconds_until_market_open()
        countdown_str = "Opens: " + format_countdown(countdown_seconds)
        screen.text(countdown_str, center_x(countdown_str), 85)
    else:
        # Show last update time
        ms_ago = time.ticks_ms() - state["last_update"]
        last_update_str = "Updated: " + format_last_update(ms_ago)
        screen.text(last_update_str, center_x(last_update_str), 85)

    # --- Stock index indicator (y=100) with live indicator ---
    screen.font = small_font
    screen.pen = COLOR_DIM
    index_str = str(state["current_stock_index"] + 1) + "/" + str(len(stocks))
    
    # Add animated "live" indicator during market hours
    if market_open:
        live_indicator = " •"
        # Pulse the dot during market hours
        live_alpha = get_pulse_alpha(current_ms, 1500)  # Faster pulse (1.5s) for the dot
        if live_alpha > 0.75:  # Only show dot when bright enough
            screen.text(index_str + live_indicator, center_x(index_str + live_indicator), 100)
        else:
            screen.text(index_str, center_x(index_str), 100)
    else:
        screen.text(index_str, center_x(index_str), 100)


def init():
    for ticker in stocks:
        if ticker not in state["stock_data"]:
            state["stock_data"][ticker] = MOCK_STOCK_DATA.get(ticker, MOCK_STOCK_DATA["TSLA"])
    State.save("stocks", state)


def update():
    global stocks_state, last_data_fetch_attempt, wifi_connect_started, state

    wifi.tick()

    # Button navigation
    if io.BUTTON_A in io.pressed or io.BUTTON_UP in io.pressed:
        state["current_stock_index"] -= 1
        if state["current_stock_index"] < 0:
            state["current_stock_index"] = len(stocks) - 1
        State.save("stocks", state)

    if io.BUTTON_C in io.pressed or io.BUTTON_DOWN in io.pressed:
        state["current_stock_index"] += 1
        if state["current_stock_index"] >= len(stocks):
            state["current_stock_index"] = 0
        State.save("stocks", state)

    # Button B: manual refresh
    if io.BUTTON_B in io.pressed:
        if stocks_state == StocksState.Running:
            print("[stocks] Button B pressed, triggering refresh")
            stocks_state = StocksState.ConnectWiFi
            wifi_connect_started = time.ticks_ms()

    # State machine
    current_time = time.ticks_ms()

    if stocks_state == StocksState.Running:
        if current_time - state["last_update"] >= UPDATE_INTERVAL:
            print("[stocks] auto-update interval hit, going to ConnectWiFi")
            user_message("Stocks Update", ["Initializing", "WiFi connection..."])
            stocks_state = StocksState.ConnectWiFi
            wifi_connect_started = current_time
        else:
            state["wifi_connected"] = wifi.is_connected()

    elif stocks_state == StocksState.ConnectWiFi:
        elapsed = current_time - wifi_connect_started
        user_message("Connecting", ["WiFi...", str(elapsed // 1000) + "s..."])

        if wifi.is_connected():
            print("[stocks] wifi.is_connected() true -> WiFiConnected")
            stocks_state = StocksState.WiFiConnected
            state["wifi_connected"] = True
        elif wifi.connect():
            print("[stocks] wifi.connect() returned truthy -> WiFiConnected")
            stocks_state = StocksState.WiFiConnected
            state["wifi_connected"] = True
        elif elapsed >= WIFI_TIMEOUT:
            print("[stocks] wifi timeout hit, giving up")
            user_message("Connection Failed", ["WiFi unavailable", "Using cached data..."])
            stocks_state = StocksState.Running
            state["wifi_connected"] = False
        # else: stay in ConnectWiFi, retry next frame

    elif stocks_state == StocksState.WiFiConnected:
        print("[stocks] state=WiFiConnected -> FetchData")
        user_message("WiFi Connected", ["Fetching stock", "prices..."])
        stocks_state = StocksState.FetchData

    elif stocks_state == StocksState.FetchData:
        print("[stocks] state=FetchData, calling fetch_all_stocks()...")
        fetch_all_stocks()
        user_message("Update Complete", ["Stock data", "refreshed!"])
        stocks_state = StocksState.Running
        state["wifi_connected"] = True

    # Draw every frame
    draw_stock_display()


def on_exit():
    pass


# Standalone support for Thonny debugging
if __name__ == "__main__":
    run(update, init=init, on_exit=on_exit)

