# 🖼️ Samsung Frame TV Art Mode Forcer

Automatically return your **2024+ Samsung Frame TV** to **Art Mode** when your **Apple TV** turns off.  
**Author:** [bc-bane](https://github.com/bc-bane)  
**Inspired by:** [donkthemagicllama’s original Gist](https://gist.github.com/donkthemagicllama/6a74d97dcc38f7bbb18ae3031059fe21)  
**Platform tested:** Orange Pi Zero 3 (Armbian Bookworm)  
**Works with:** 2024 Samsung The Frame TV + Apple TV 4K (tvOS 18+)  

---

Do you have an Apple TV that forces your Samsung Frame TV to turn off to a black screen instead of into Art mode?
Do you have a spare raspberry pi over there with nothing to do?
Well fear not now you can put it to use and dedicate that pi to being a little worker that flips your Frame TV into Art Mode anytime it notices that the Apple TV turns off.

## 🧩 Why this exists
Newer Frame TVs (2024 models onward) no longer return to **Art Mode** automatically when powered off via HDMI-CEC (for example, when an Apple TV sleeps).  
This small daemon monitors your Apple TV power state and triggers Art Mode reliably after shutdown.

---

## Why not use a SmartThings Automations

A commonly suggested workaround is to use a **SmartThings routine** to force the Samsung *The Frame* back into Art Mode whenever it’s turned off.  
Unfortunately, this approach has multiple drawbacks:

- **Motion Sensor & Night Mode Conflict**  
  Because the routine activates whenever the TV turns off, it overrides the built-in motion sensor and Night Mode behavior.  
  The TV may immediately turn back on (in Art Mode) even when it should stay off.

- **HDMI-CEC / Anynet+ Instability**  
  Users report that repeated SmartThings automations can cause HDMI-CEC (Anynet+) to become unreliable or break entirely —  
  volume controls stop responding, inputs fail to switch, and in some cases the TV requires a factory reset.  

  > “When powering down the Apple TV with the Siri remote, the Frame TV shuts off but does not go into Art Mode.”  
  > — [Samsung Community Thread](https://us.community.samsung.com/t5/QLED-and-The-Frame-TVs/Apple-TV-remote-Art-Mode/td-p/3301453)

  > “Frame TV automatically turns on in Art Mode … it may be due to SmartThings.”  
  > — [Samsung Support Article](https://www.samsung.com/us/support/troubleshooting/TSG01216243/)

  > “There is no option to turn the Frame directly into Art Mode via a SmartThings scene.”  
  > — [SmartThings Community Discussion](https://community.smartthings.com/t/make-a-scene-to-art-mode-using-smartthings-and-the-frame-tv/197103)

- **Unintended Flips / Boot Loops**  
  Because SmartThings remains active while the TV is off, the Frame may unintentionally wake itself — sometimes repeatedly.  
  This can cause increased power usage, wear on components, and erratic “phantom wake” behavior.

Because of these issues, the SmartThings automation path tends to be fragile for the Frame + Apple TV use-case.  
This project offers a **more reliable alternative** by using direct network control via WebSocket/API,  
avoiding SmartThings entirely while preserving motion and CEC functionality.

---

## 🪴 Hardware setup
| Component | Notes |
|------------|-------|
| **Single-board computer** | Orange Pi Zero 3 (Raspberry Pi Zero W 2, Banana Pi Berry, etc.) |
| **Storage** | Micro-SD card (≥ 8 GB) |
| **Network** | Ethernet recommended (same subnet as Apple TV + Frame TV) |
| **Power** | 5 V USB-C adapter ≥ 2 A |

---

## 🌐 Network setup
1. Connect your **Apple TV** and **Frame TV** to your router via **Ethernet**. (Wi-Fi *may* work if all devices are on the same subnet, but mesh networks can cause discovery failures.)  
2. Assign **static local IPs** to both devices in your router’s admin panel. This ensures reliable communication between the Pi, Apple TV, and Frame TV.
3. After Flashing my Pi and plugging it in I also assign it a static IP so that it is very easy to log into later

---

## ⚙️ Software setup

### 1️⃣ Flash Armbian or Debian
Download the latest **Armbian Bookworm** for your board:  
👉 https://www.armbian.com/download  

Flash using **balenaEtcher** or **Raspberry Pi Imager**, then boot and complete setup (`root` → create user).

### 2️⃣ Enable SSH (optional GUI-less setup)
```bash
sudo apt update && sudo apt install -y openssh-server
ssh youruser@orangepi.local
# or: ssh root@192.168.68.XX replace with the static IP of your Pi computer
```

### 3️⃣ Create Python virtual environment
```bash
sudo apt install -y python3-venv python3-dev build-essential
python3 -m venv ~/frameenv
source ~/frameenv/bin/activate
pip install --upgrade pip
```

### 4️⃣ Install dependencies
```bash
pip install pyatv samsungtvws urllib3
```

### 5️⃣ Pair with Apple TV
Scan for your Apple TV (replace IP as needed):
```bash
python -m pyatv.scripts.atvremote --scan-hosts 192.168.68.XX scan # Replace with your Apple TV's static IP
```

Run the pairing wizard:
```bash
python -m pyatv.scripts.atvremote --scan-hosts 192.168.68.XX wizard # Replace with your Apple TV's static IP
```

Copy the resulting **Apple TV Identifier (UUID)** for later.

### 6️⃣ Pair with Frame TV
Run inside a Python REPL:
```python
from samsungtvws import SamsungTVWS
tv = SamsungTVWS(host="192.168.68.XX", port=8002, token_file="frame_token.txt") # Replace with your Frame TV's static IP
tv.shortcuts().power()  # Accept the pairing prompt on the TV
```

A `frame_token.txt` file will be created in your home directory.

### 7️⃣ Clone this repository
```bash
git clone https://github.com/bc-bane/frameTVArtModePi.git
cd frameTVArtModePi
```

### 8️⃣ Edit configuration
Edit `watcher.py` and set:
```python
FRAME_IP  = "192.168.68.XX"              # Replace with your Frame TV's static IP
TOKEN_FILE = "/home/youruser/frame_token.txt"  # Confirm file location
ATV_ID     = "YOUR-APPLE-TV-ID"          # Replace with the Apple TV ID from earlier
```

### 9️⃣ Test manually
```bash
source ~/frameenv/bin/activate
python watcher.py
```
Turn your Apple TV on/off — your Frame should switch to Art Mode within ~5 seconds after shutdown.

### 🔟 Run automatically via systemd
Create a service file:
```bash
sudo nano /etc/systemd/system/framewatcher.service
```

Paste:
```ini
[Unit]
Description=Apple TV → Samsung Frame Art Mode Watcher
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/home/youruser/frameenv/bin/python /home/youruser/frameTVArtModePi/watcher.py
Restart=always
User=youruser
WorkingDirectory=/home/youruser/frameTVArtModePi
StandardOutput=append:/var/log/framewatcher.log
StandardError=append:/var/log/framewatcher.log

[Install]
WantedBy=multi-user.target
```

Enable & start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable framewatcher
sudo systemctl start framewatcher
sudo journalctl -u framewatcher -f
```

---

## 🧠 How it works
1. **pyatv** polls the Apple TV’s Companion protocol for `power_state`.  
2. When Apple TV powers off → script waits 5 seconds.  
3. The script sends `samsungtvws.shortcuts().power()` to the Frame TV until Art Mode = `"on"`.  
4. Lost WebSocket sessions are auto-recovered by reinitializing connections.

---

## 🪵 Logs & troubleshooting
View logs anytime:
```bash
sudo journalctl -u framewatcher -n 50
```

| Message                        | Meaning                                        |
|--------------------------------|------------------------------------------------|
| `No route to host`             | TV temporarily offline; will retry.           |
| `Art mode successfully enabled`| Success 🎉                                    |
| `Gave up after 5 attempts`     | TV unresponsive — check subnet + static IP.   |

---

Monitor live:
```bash
htop
```

---

## 🙌 Credits
Credit appreciated: [donkthemagicllama](https://gist.github.com/donkthemagicllama)  
Special thanks to the open-source Python community ❤️
