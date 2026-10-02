#!/usr/bin/env python3
"""ThermoX receiver: reads lines from the ESP32's Bluetooth serial port and
forwards each one to the PHP API (api/log.php).

Pair the ESP32 ("ThermoX") with your PC first; the OS then exposes a serial port
(Windows: an outgoing COM port, Linux: /dev/rfcomm0). Example:

    python receiver.py --list-ports
    python receiver.py --port COM5 --url http://localhost/thermox/api/log.php --key YOUR_API_KEY
"""
import argparse
import os
import sys
import time
import urllib.error
import urllib.request

import serial
import serial.tools.list_ports


def post_line(url, key, line):
    req = urllib.request.Request(
        url, data=line.encode("ascii", "ignore"), method="POST",
        headers={"Content-Type": "text/plain", "X-API-Key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:200]
    except OSError as e:
        return 0, str(e)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="Bluetooth serial port, e.g. COM5 or /dev/rfcomm0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--url", default="http://localhost/thermox/api/log.php")
    ap.add_argument("--key", default=os.environ.get("THERMOX_API_KEY", ""),
                    help="API key (or set THERMOX_API_KEY); must match api_key in config.php")
    ap.add_argument("--list-ports", action="store_true")
    a = ap.parse_args()

    if a.list_ports:
        for p in serial.tools.list_ports.comports():
            print(p.device, "-", p.description)
        return
    if not a.port or not a.key:
        ap.error("--port and --key (or THERMOX_API_KEY) are required")

    while True:
        try:
            with serial.Serial(a.port, a.baud, timeout=2) as ser:
                print("Connected to", a.port)
                while True:
                    raw = ser.readline().decode("ascii", "ignore").strip()
                    if not raw.startswith("TEMP="):   # ignore blanks and boot messages
                        continue
                    status, err = post_line(a.url, a.key, raw)
                    print(time.strftime("%H:%M:%S"), raw, "->", "stored" if status == 201 else f"HTTP {status} {err}")
        except serial.SerialException as e:
            print("Serial error:", e, "- retrying in 5 s", file=sys.stderr)
            time.sleep(5)
        except KeyboardInterrupt:
            print("Stopped.")
            return


if __name__ == "__main__":
    main()
