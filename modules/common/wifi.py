import network
from badgeware import fatal_error

_timeout = None
_on_success = None
_on_error = None
wlan = None


_status_text = {
  0: "Idle",
  1: "Connecting to {ssid}",
  -3: "Incorrect password.",
  -2: "Access point {ssid} not found.",
  -1: "Connection failed.",
  3: "Got IP",
}


def get_status(index):
  return _status_text[index].format(ssid=_ssid, psk=_psk)


def tick():
  global _timeout, _on_success, _on_error

  if wlan is not None and wlan.isconnected():
    if _on_success:
      _on_success()
      _timeout = None
      _on_success = None
      _on_error = None
    return

  timed_out = _timeout is not None and io.ticks > _timeout
  error = wlan is not None and wlan.status() not in (0, 1, 3)

  if (timed_out or error):
    wlan.active(False)
    _timeout = None
    if _on_error:
      _on_error()
    else:
      fatal_error("WiFi Connection Failed", get_status(wlan.status()))
    # connection timeout
    _on_success = None
    _on_error = None


def connect(ssid=None, psk=None, timeout=60, on_success=None, on_error=None):
  global wlan, _timeout, _on_success, _on_error, _ssid, _psk

  if ssid is None and psk is None:
    secrets = __import__("/system/secrets")
    ssid = secrets.WIFI_SSID
    psk = secrets.WIFI_PASSWORD

    if not ssid:
      fatal_error("Missing Details!", "Put your badge into disk mode (tap RESET twice)\nEdit 'secrets.py' to set WiFi details and your local region")

  _ssid = ssid
  _psk = psk

  if wlan and wlan.isconnected():
    return True

  if wlan is None:
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, psk)
    _on_success = on_success
    _on_error = on_error
    _timeout = io.ticks + (timeout * 1000)

  return False


def status():
  global wifi
  if wifi is None:
    return 0, get_status(0)  # Idle
  return wlan.status(), get_status(wlan.status())


def is_connected():
  return wlan is not None and wlan.isconnected()


def ipv4():
  return wlan.ipconfig("addr4")[0] if wlan else None


def ipv6():
  return wlan.ipconfig("addr6")[0][0] if wlan else None


def ip():
  return ipv4()


def subnet():
  return wlan.ifconfig()[1] if wlan else None


def gateway():
  return wlan.ifconfig()[2] if wlan else None


def nameserver():
  return wlan.ifconfig()[3] if wlan else None
