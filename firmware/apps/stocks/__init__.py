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
}

State.load("stocks", state)

stocks_state = StocksState.ConnectWiFi
last_data_fetch_attempt = time.ticks_ms()
wifi_connect_started = time.ticks_ms()

UPDATE_INTERVAL = 300000   # 5 minutes in ms
WIFI_TIMEOUT = 10000       # 10 seconds before giving up on wifi

# Colors
COLOR_UP = color.rgb(0, 255, 0)
COLOR_DOWN = color.rgb(255, 0, 0)
COLOR_NEUTRAL = color.rgb(200, 200, 200)
COLOR_BG = color.rgb(0, 0, 0)
COLOR_TEXT = color.rgb(255, 255, 255)
COLOR_DIM = color.rgb(100, 100, 100)

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
    """Draw the main stock display. Screen is 160x120."""
    screen.pen = COLOR_BG
    screen.clear()

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

    # --- Ticker symbol (y=10) ---
    screen.font = large_font
    screen.pen = COLOR_TEXT
    ticker_label = ticker
    if state["wifi_connected"]:
        ticker_label = ticker + " [W]"
    screen.text(ticker_label, center_x(ticker_label), 10)

    # --- Price (y=34) ---
    screen.font = large_font
    price_str = fmt_price(price)
    screen.pen = COLOR_TEXT
    screen.text(price_str, center_x(price_str), 34)

    # --- Change line (y=58) ---
    screen.font = small_font
    change_str = direction + " " + fmt_change(change) + " (" + fmt_percent(change_percent) + ")"
    screen.pen = change_color
    screen.text(change_str, center_x(change_str), 58)

    # --- WiFi status (y=80) ---
    screen.font = small_font
    screen.pen = COLOR_DIM
    if state["wifi_connected"]:
        wifi_str = "WiFi: Connected"
    else:
        wifi_str = "WiFi: Offline"
    screen.text(wifi_str, center_x(wifi_str), 80)

    # --- Stock index indicator (y=96) ---
    index_str = str(state["current_stock_index"] + 1) + "/" + str(len(stocks))
    screen.pen = COLOR_DIM
    screen.text(index_str, center_x(index_str), 96)


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

