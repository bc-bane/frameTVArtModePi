🖼️ # Samsung Frame TV Art Mode Forcer
Automatically return your 2024+ Frame TV to Art Mode when Apple TV turns off
Author: bc-baneInspired by: donkthemagicllama’s original Gist
Platform tested: Orange Pi Zero 3 (Armbian Bookworm)
Works with: 2024 Samsung The Frame TV + Apple TV 4K (tvOS 18+)

🧩 Why this exists
Newer Frame TVs (2024 models onward) no longer return to Art Mode automatically when powered off via HDMI-CEC (for example, when an Apple TV sleeps).
This small daemon monitors your Apple TV power state and triggers Art Mode reliably after shutdown — without breaking CEC or motion-sensor features.

🪴 Hardware setup
ComponentNotesSingle-board computerOrange Pi Zero 3 (Raspberry Pi Zero W 2, Banana Pi Berry, etc.)StorageMicro-SD card (≥ 8 GB)NetworkEthernet recommended (same subnet as Apple TV + Frame TV)Power5 V USB-C adapter ≥ 2 A

🌐 Network setup
1. Connect your Apple TV and your Frame TV to your router via ethernet (may be possible if all devices on the same Wi-Fi network, but I was unsuccessful. Likley due to Mesh network)
2. In your network settings make sure that each device has a static local ip as that will ensure they can talk to eachother

⚙️ Software setup
1. Flash Armbian or Debian
Download the latest Armbian Bookworm for your board
→ https://www.armbian.com/download
Flash using balenaEtcher or Raspberry Pi Imager.
Boot and complete the on-screen setup (root → create user).

2. Enable SSH (optional GUI-less setup)
`sudo apt update && sudo apt install -y openssh-server`
`ssh youruser@orangepi.local`


3. Create Python virtual environment
`sudo apt install -y python3-venv python3-dev build-essential`
`python3 -m venv ~/frameenv`
`source ~/frameenv/bin/activate`
`pip install --upgrade pip`


4. Install dependencies
`pip install pyatv samsungtvws urllib3`


5. Pair with Apple TV
Scan for your Apple TV:
# replace 192.168.68.80 with the static ip address of your Apple TV
`python -m pyatv.scripts.atvremote --scan-hosts 192.168.68.80 scan`

Run the pairing wizard:
# replace 192.168.68.80 with the static ip address of your Apple TV
`python -m pyatv.scripts.atvremote --scan-hosts 192.168.68.80 wizard`

Copy the resulting Apple TV Identifier (UUID) for later.

6. Pair with Frame TV
Run inside Python REPL:
`from samsungtvws import SamsungTVWS`
# replace 192.168.68.78 with the static ip address of your Frame TV
`tv = SamsungTVWS(host="192.168.68.78", port=8002, token_file="frame_token.txt")`
`tv.shortcuts().power()`  # Accept the pairing prompt on the TV

A frame_token.txt file will be created in your home directory.

7. Clone this repo
`git clone https://github.com/bc-bane/frameTVArtModePi.git`
`cd frameTVArtModePi`


8. Edit configuration
# replace 192.168.68.78 with the static ip address of your Frame TV
Inside watcher.py, set:
FRAME_IP  = "192.168.68.78"
TOKEN_FILE = "/home/youruser/frame_token.txt" # confirm this file location
ATV_ID     = "YOUR-APPLE-TV-ID" # replace with the id from the Apple TV setup earlier


10. Test manually
`source ~/frameenv/bin/activate`
`python watcher.py`

Turn the Apple TV on/off — your Frame should switch to Art Mode within ~5 seconds after shutdown.

10. Run automatically via systemd
Create service file:
`sudo nano /etc/systemd/system/framewatcher.service`

Paste:
[Unit]
Description=Apple TV → Samsung Frame Art Mode Watcher
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/home/bob/frameenv/bin/python /home/bob/frameforcer/watcher.py
Restart=always
User=youruser
WorkingDirectory=/home/youruser/frameforcer
StandardOutput=append:/var/log/framewatcher.log
StandardError=append:/var/log/framewatcher.log

[Install]
WantedBy=multi-user.target

Enable & start:
sudo systemctl daemon-reload
sudo systemctl enable framewatcher
sudo systemctl start framewatcher
sudo journalctl -u framewatcher -f


🧠 How it works


pyatv polls Apple TV’s Companion protocol for power_state.


When Apple TV goes off → script waits 5 s.


Script issues a fresh samsungtvws.shortcuts().power() to the Frame, repeating until Art Mode = “on”.


Handles lost WebSocket sessions by re-creating connections every call.



🪵 Logs & troubleshooting
Check logs anytime:
sudo journalctl -u framewatcher -n 50

Common messages:
MessageMeaningNo route to hostTV temporarily offline; will retry.Art mode successfully enabledSuccess 🎉Gave up after 5 attemptsTV unresponsive — ensure same subnet + static IP.

🔍 Performance
On Orange Pi Zero 3:


CPU usage ≈ 3–5 %


RAM ≈ 70–90 MB


Idle load ≈ 0.1


Monitor live:
htop


Credit appreciated: donkthemagicllama
