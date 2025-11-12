#!/usr/bin/env python3
"""
Apple TV → Samsung Frame Art Mode watcher

- Polls Apple TV power state via pyatv CLI (atvremote), first with Companion,
  then falls back to AirPlay (more tolerant when ATV is sleepy).
- When Apple TV turns OFF, waits a bit, then restores Frame TV Art Mode.
- Always uses *fresh* SamsungTVWS connections to avoid stale sockets.
- Prints timestamped logs and never crashes the main loop.
"""

import sys
import time
import subprocess
from datetime import datetime

from samsungtvws import SamsungTVWS
import urllib3

urllib3.disable_warnings()

# === USER CONFIG ======================================================

# Frame TV (static IP recommended)
FRAME_IP = "192.168.68.XX"          # <-- set me, e.g. "192.168.68.78"

# Path to the token file you created when pairing with the Frame
TOKEN_FILE = "/home/youruser/frame_token.txt"   # <-- set me

# Apple TV identifier from `python -m pyatv.scripts.atvremote --scan-hosts ... wizard`
ATV_ID = "YOUR-APPLE-TV-ID"         # <-- set me

# (Optional) Apple TV static IP; speeds up atvremote and avoids discovery flakiness
ATV_IP = "192.168.68.XX"            # <-- set me (recommended)

# How long to wait after Apple TV turns off before touching the Frame (seconds)
WAIT_AFTER_ATV_OFF = 5

# How many attempts to make when trying to enable art mode
ART_MODE_MAX_ATTEMPTS = 5

# ======================================================================


def log(msg: str) -> None:
    """Print with timestamp so journal logs are easy to scan."""
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {msg}", flush=True)


def get_tv() -> SamsungTVWS:
    """
    Create a *fresh* SamsungTVWS instance each time.

    This avoids issues where a long-lived connection goes stale and
    starts throwing `[Errno 113] No route to host` even though the TV
    is reachable again.
    """
    return SamsungTVWS(host=FRAME_IP, port=8002, token_file=TOKEN_FILE)


def _atvremote_power_state(protocol: str, timeout: int = 5) -> str:
    """
    Call pyatv's atvremote once and return its stdout (or "" on error/timeout).
    Suppresses stderr to avoid noisy asyncio tracebacks in systemd logs.
    """
    args = [
        sys.executable, "-m", "pyatv.scripts.atvremote",
        "--id", ATV_ID,
        "--protocol", protocol,              # "companion" or "airplay"
        "power_state",
    ]
    # If you know the ATV IP, pass it to skip network discovery
    if ATV_IP:
        args[5:5] = ["--address", ATV_IP]

    try:
        out = subprocess.check_output(
            args,
            text=True,
            timeout=timeout,
            stderr=subprocess.DEVNULL,
        ).strip()
        return out
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def atv_on(max_retries: int = 5) -> bool:
    """
    Return True if Apple TV is ON, False otherwise.

    Strategy:
      1) Try Companion twice (fast/accurate when ATV is awake).
      2) Fall back to AirPlay for the remaining tries (often works from light/deep sleep).
      3) Short sleeps and total bound on retries to keep loop responsive.
    """
    # Companion fast path (2 tries)
    for attempt in range(1, min(2, max_retries) + 1):
        out = _atvremote_power_state("companion")
        if out:
            if "On" in out:
                return True
            if "Off" in out or "Standby" in out:
                return False
        if attempt > 1:
            log(f"tv companion read failed (attempt {attempt}) -> {out!r}")
        time.sleep(1)

    # AirPlay fallback
    for attempt in range(1, max_retries + 1):
        out = _atvremote_power_state("airplay")
        if out:
            if "On" in out:
                return True
            if "Off" in out or "Standby" in out:
                return False
        if attempt > 1:
            log(f"tv airplay read failed (attempt {attempt}) -> {out!r}")
        time.sleep(1)

    log(f"tv power_state unresolved after {max_retries} airplay attempts → assuming OFF")
    return False


def tv_status() -> str:
    """
    Return Frame TV power state string, e.g. 'on', 'standby', or 'unknown'.
    Uses a *fresh* SamsungTVWS connection to avoid stale sockets.
    """
    try:
        tv = get_tv()
        info = tv.rest_device_info()
        state = info["device"].get("PowerState", "unknown")
        return (state or "unknown").lower()
    except Exception as e:
        log(f"Error getting TV status: {e}")
        return "unknown"


def art_mode_is_on(max_retries: int = 20) -> bool:
    """
    Check if Frame is currently in Art Mode.

    Returns:
        True if art mode is on
        False if explicitly off, or if retries are exhausted.

    max_retries mainly avoids infinite loops if the TV vanishes
    from the network or keeps sending non-standard messages.
    """
    retries = 0
    while retries < max_retries:
        try:
            tv = get_tv()
            mode = tv.art().get_artmode()
            if mode in ("on", "off"):
                return mode == "on"
        except Exception as e:
            # Samsung sometimes sends event payloads instead of simple on/off,
            # and sometimes the TV is simply unreachable.
            log(f"Error getting art mode: {e}")

        retries += 1
        if retries > 1:
            log(f"Art mode check retry {retries}, TV status: {tv_status()}")
        time.sleep(1)

    log("Art mode check gave up after max retries.")
    return False


def tv_power_toggle() -> None:
    """Toggle TV power / Art mode via shortcuts().power()."""
    try:
        tv = get_tv()
        tv.shortcuts().power()
    except Exception as e:
        log(f"Error toggling TV power: {e}")


def main() -> None:
    log("Frame watcher started.")
    atv_has_been_on = False
    tv_has_been_sleeping = False

    while True:
        try:
            atv_state = atv_on()
            status = tv_status()

            # Apple TV is ON and Frame is not in deep standby
            if atv_state and status != "standby":
                if not atv_has_been_on:
                    log("tv turned ON")
                atv_has_been_on = True
                tv_has_been_sleeping = False

                # Poll more frequently when ATV is on (more responsive)
                time.sleep(0.5)

            # Apple TV is OFF or in standby
            elif not atv_state:
                # If we're already in art mode, just chill
                if art_mode_is_on(max_retries=5):
                    time.sleep(2)
                else:
                    if atv_has_been_on:
                        log("tv turned OFF → restoring Art Mode")
                        atv_has_been_on = False

                        # Give the Frame time to finish HDMI/CEC power-down
                        log(f"  - Waiting {WAIT_AFTER_ATV_OFF} seconds for Frame to settle...")
                        time.sleep(WAIT_AFTER_ATV_OFF)

                        # Try up to ART_MODE_MAX_ATTEMPTS times to ensure Art Mode sticks
                        for attempt in range(1, ART_MODE_MAX_ATTEMPTS + 1):
                            log(f"  - Attempt {attempt}: toggling power & checking Art Mode")
                            tv_power_toggle()
                            time.sleep(3)

                            if art_mode_is_on(max_retries=5):
                                log("✅ Art mode successfully enabled.")
                                break

                            log("  - Art mode still off, waiting before retry...")
                            time.sleep(3)
                        else:
                            log("❌ Gave up trying to restore Art Mode after max attempts")
                    else:
                        # Apple TV might be on again but Frame in standby
                        if atv_state and status == "standby":
                            log("tv ON but Frame in standby → waking Frame")
                            tv_power_toggle()
                            time.sleep(2)
                        else:
                            if not tv_has_been_sleeping:
                                log("Frame appears to be sleeping")
                            tv_has_been_sleeping = True
                            # ATV off and Frame sleeping: check less often
                            time.sleep(2)

            # Fallback: should rarely hit here, but don't spin hot
            else:
                time.sleep(1)

        except Exception as e:
            # Log and keep going; avoid crash loops
            log(f"[watcher loop] Unexpected error: {e}")
            time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopping watcher.")
