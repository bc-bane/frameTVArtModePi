#!/usr/bin/env python3
import asyncio
import time
from samsungtvws import SamsungTVWS
import urllib3
from pyatv import scan, connect, exceptions
from pyatv.interface import PowerState

urllib3.disable_warnings()

# === CONFIGURATION ===
FRAME_IP = "192.168.68.78"  # Replace with your Frame TV's static IP
TOKEN_FILE = "/home/youruser/frame_token.txt"  # Path to your Samsung token
ATV_ID = "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"  # Replace with your Apple TV identifier

# === INITIALIZE FRAME TV ===
tv = SamsungTVWS(host=FRAME_IP, port=8002, token_file=TOKEN_FILE)

# === APPLE TV STATE CHECK ===
def atv_on():
    """Return True if Apple TV is currently on."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        devices = loop.run_until_complete(scan(loop, hosts=[FRAME_IP[:-2] + "80"]))
        for conf in devices:
            if conf.identifier == ATV_ID:
                atv = loop.run_until_complete(connect(conf, loop))
                power_state = atv.power.power_state
                loop.run_until_complete(atv.close())
                return power_state == PowerState.On
        return False
    except Exception:
        return False


# === SAMSUNG FRAME HELPERS ===
def tv_status():
    """Check Frame TV current power status."""
    try:
        info = tv.rest_device_info()
        return info["device"]["PowerState"].lower()
    except Exception:
        return "unknown"


def art_mode_is_on():
    """Check if Frame is currently in Art Mode."""
    retries = 0
    while True:
        try:
            mode = tv.art().get_artmode()
            if mode in ("on", "off"):
                return mode == "on"
        except Exception as e:
            print(f"Error getting art mode: {e}")

        retries += 1
        if retries > 1:
            print(f"Art mode check retry {retries}, TV status: {tv_status()}")
        time.sleep(1)


def tv_power_toggle():
    """Toggle TV power/Art mode via shortcuts().power()."""
    try:
        tv.shortcuts().power()
    except Exception as e:
        print(f"Error toggling TV power: {e}")


# === MAIN LOOP ===
def main():
    print("Frame watcher started.")
    atv_has_been_on = False
    tv_has_been_sleeping = False

    while True:
        atv_state = atv_on()
        status = tv_status()

        # Apple TV is ON
        if atv_state and status != "standby":
            if not atv_has_been_on:
                print("tv turned ON")
            atv_has_been_on = True
            tv_has_been_sleeping = False
            time.sleep(0.5)  # faster poll when active

        # Apple TV turned OFF
        elif not atv_state and atv_has_been_on:
            print("tv turned OFF → restoring Art Mode")
            atv_has_been_on = False

            print("  - Waiting 5 seconds for Frame to settle...")
            time.sleep(5)

            # Try toggling Frame to Art Mode
            for attempt in range(1, 6):
                print(f"  - Attempt {attempt}: toggling power & checking Art Mode")
                tv_power_toggle()
                time.sleep(5)

                if art_mode_is_on():
                    print("✅ Art mode successfully enabled.")
                    break
                else:
                    print("  - Art mode still off, waiting before retry...")
                    time.sleep(3)
            else:
                print("❌ Gave up after 5 attempts — TV may be unreachable or CEC conflict.")

        else:
            # idle polling
            time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopping watcher.")
