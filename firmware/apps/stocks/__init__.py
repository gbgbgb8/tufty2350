# Stocks app for Tufty2350
APP_DIR = "/system/apps/stocks"

import sys
import os
import time
import wifi
import secrets

# Standalone bootstrap for finding app assets
os.chdir(APP_DIR)

# Standalone bootstrap for module imports
sys.path.insert(0, APP_DIR)

from badgeware import run, State

# Generate icon if it doesn't exist (base64 encoded 32x32 PNG)
icon_path = os.path.join(APP_DIR, "icon.png")
if not os.path.exists(icon_path):
    import base64
    icon_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAyElEQVR42u2YQQrAMAwDNZWDHkT8h/0fpx7Eg4cRPIoH8SAe5iDeRPygHsSDhJF4EA/iQTyIB/EgXsSDeBAPwgH+EzG3KMzd2Ww2m81mM/PnP2+z2Ww2m80YY9M0lSQBUFVV13UlSYIxZls2bZskSQpBwHVdXdedd56WJWmaJkmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJP+GZLP5j9lsNv+p6xrHcRzHcRzHcRzHcRzHcRzHcRyHMQZjDMYYjDEYYzDGAAwDAAz/hf8fKxRWAStU5hsqFFYBK1TmGyoUVgErVOYbKhRWAStU5hsqFFYBK1TmGyoUVgErVOYbKhRWAStU5g8qFFYBK1TmDyoUVgErVOYPKhRWAStU5g8qFFYBK1TmDyoUVgErVOYPKhRWAStU5g8qFFYBK1TmHyoUVgErVOY3VCisAlatDXQAAAAASUVORK5CYII="
    )
    try:
        with open(icon_path, "wb") as f:
            f.write(icon_data)
    except Exception:
        pass  # If icon can't be created, the app will still work

# Import stocks list from secrets
try:
    stocks = secrets.STOCKS
except AttributeError:
    stocks = ["TSLA", "PLTR", "SPY", "QQQ"]

# App state
state = {
    "current_stock_index": 0,
    "stock_data": {},
    "last_update": 0,
    "wifi_connected": False,
}

State.load("stocks", state)

# Colors
COLOR_UP = color.rgb(0, 255, 0)
COLOR_DOWN = color.rgb(255, 0, 0)
COLOR_NEUTRAL = color.rgb(200, 200, 200)
COLOR_BG = color.rgb(0, 0, 0)
COLOR_TEXT = color.rgb(255, 255, 255)

# Fonts
large_font = pixel_font.load("/system/assets/fonts/smart.ppf")
small_font = pixel_font.load("/system/assets/fonts/fear.ppf")

screen.antialias = image.X2

# Mock stock data for fallback
MOCK_STOCK_DATA = {
    "TSLA": {"price": 420.00, "change": 5.25, "change_percent": 1.26},
    "PLTR": {"price": 35.50, "change": 0.75, "change_percent": 2.15},
    "SPY": {"price": 385.20, "change": -2.10, "change_percent": -0.54},
    "QQQ": {"price": 315.75, "change": 3.45, "change_percent": 1.10},
}

UPDATE_INTERVAL = 300  # Update every 5 minutes


def fetch_stock_data(ticker):
    """Fetch stock data, using mock data as fallback."""
    if not wifi.is_connected():
        state["wifi_connected"] = False
        return MOCK_STOCK_DATA.get(ticker, MOCK_STOCK_DATA["TSLA"])
    
    state["wifi_connected"] = True
    
    try:
        import urequests
        api_key = getattr(secrets, 'ALPHA_VANTAGE_KEY', 'demo')
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={api_key}"
        response = urequests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if "Global Quote" in data:
                quote = data["Global Quote"]
                if "05. price" in quote:
                    price = float(quote.get("05. price", 0))
                    change = float(quote.get("09. change", 0))
                    change_percent = float(quote.get("10. change percent", "0").rstrip("%"))
                    return {
                        "price": price,
                        "change": change,
                        "change_percent": change_percent
                    }
    except ImportError:
        pass
    except Exception:
        pass
    
    # Fallback to mock data
    return MOCK_STOCK_DATA.get(ticker, MOCK_STOCK_DATA["TSLA"])


def update_stock_data():
    """Update stock data for all stocks in the list."""
    current_time = time.time()
    
    # Only update if enough time has passed
    if current_time - state["last_update"] < UPDATE_INTERVAL:
        return
    
    for ticker in stocks:
        try:
            state["stock_data"][ticker] = fetch_stock_data(ticker)
        except Exception:
            # Use mock data as fallback
            state["stock_data"][ticker] = MOCK_STOCK_DATA.get(ticker, MOCK_STOCK_DATA["TSLA"])
    
    state["last_update"] = current_time
    State.save("stocks", state)


def get_current_stock():
    """Get the current stock being displayed."""
    if state["current_stock_index"] >= len(stocks):
        state["current_stock_index"] = 0
    
    ticker = stocks[state["current_stock_index"]]
    
    if ticker not in state["stock_data"]:
        state["stock_data"][ticker] = MOCK_STOCK_DATA.get(ticker, MOCK_STOCK_DATA["TSLA"])
    
    return ticker, state["stock_data"][ticker]


def draw_stock_display():
    """Draw the main stock display."""
    screen.pen = COLOR_BG
    screen.clear()
    
    ticker, data = get_current_stock()
    
    price = data.get("price", 0)
    change = data.get("change", 0)
    change_percent = data.get("change_percent", 0)
    
    # Determine color based on change
    if change > 0:
        change_color = COLOR_UP
        symbol = "▲"
    elif change < 0:
        change_color = COLOR_DOWN
        symbol = "▼"
    else:
        change_color = COLOR_NEUTRAL
        symbol = "="
    
    # Draw ticker symbol (large)
    screen.font = large_font
    screen.pen = COLOR_TEXT
    ticker_width = screen.measure_text(ticker)[0]
    screen.text(ticker, (screen.width - ticker_width) // 2, 20)
    
    # Draw price (very large)
    screen.font = large_font
    price_str = f"${price:.2f}"
    price_width = screen.measure_text(price_str)[0]
    screen.text(price_str, (screen.width - price_width) // 2, 70)
    
    # Draw change with color and symbol
    screen.pen = change_color
    screen.font = small_font
    change_str = f"{symbol} {abs(change):.2f} ({change_percent:+.2f}%)"
    change_width = screen.measure_text(change_str)[0]
    screen.text(change_str, (screen.width - change_width) // 2, 130)
    
    # Draw WiFi and update status at bottom
    screen.pen = COLOR_TEXT
    screen.font = small_font
    
    status_y = 160
    if state["wifi_connected"]:
        wifi_status = "WiFi: Connected"
    else:
        wifi_status = "WiFi: Offline"
    
    wifi_width = screen.measure_text(wifi_status)[0]
    screen.text(wifi_status, (screen.width - wifi_width) // 2, status_y)
    
    # Draw stock index indicator
    status_y += 20
    index_str = f"{state['current_stock_index'] + 1}/{len(stocks)}"
    index_width = screen.measure_text(index_str)[0]
    screen.text(index_str, (screen.width - index_width) // 2, status_y)


def init():
    """Initialize the app."""
    # Load initial mock data
    for ticker in stocks:
        if ticker not in state["stock_data"]:
            state["stock_data"][ticker] = MOCK_STOCK_DATA.get(ticker, MOCK_STOCK_DATA["TSLA"])
    
    State.save("stocks", state)


def update():
    """Main update loop."""
    global state
    
    # Tick WiFi connection
    wifi.tick()
    
    # Handle button presses
    if io.BUTTON_A in io.pressed:
        # Previous stock
        state["current_stock_index"] -= 1
        if state["current_stock_index"] < 0:
            state["current_stock_index"] = len(stocks) - 1
        State.save("stocks", state)
    
    if io.BUTTON_B in io.pressed:
        # Manual refresh
        state["last_update"] = 0
        update_stock_data()
    
    if io.BUTTON_C in io.pressed:
        # Next stock
        state["current_stock_index"] += 1
        if state["current_stock_index"] >= len(stocks):
            state["current_stock_index"] = 0
        State.save("stocks", state)
    
    # Update stock data if needed
    update_stock_data()
    
    # Draw the display
    draw_stock_display()


# Run the app
run(init, update)
