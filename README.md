# gtv-debloat

A lightweight, reversible Google TV bloatware disabler. Safely remove unwanted pre-installed apps without root access, using nothing but ADB and the native `pm disable-user` command. Everything is reversible—no uninstalls, no file system tampering, no risk of soft-bricking your TV.

## Requirements

- **Python 3.9 or later**
- **Android Debug Bridge (`adb`)** from [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools) on your system PATH

To verify installation:
```bash
python --version     # Should be 3.9+
adb version         # Should print version info
```

## Enable ADB on Google TV

Follow these steps to enable debugging on your Google TV:

1. **Unlock Developer Options:**
   - Go to **Settings** > **System** > **About**
   - Find and tap **"Android TV OS build"** (or just **"Build"**) **7 times** in quick succession
   - You should see a notification: "You are now a developer"

   > The build entry's label varies by device. On some Arçelik / MediaTek sets it
   > is shown as **"Android TV OS build"** (Turkish: **"Android TV OS derlemesi"**)
   > rather than a plain "Build number."

2. **Enable USB and Network Debugging:**
   - Return to **Settings** > **System** > **Developer options**
   - Enable **USB debugging**
   - Enable **Network debugging** (if present)

3. **Find Your TV's IP Address:**
   - Go to **Settings** > **Network & Internet** > **Wi-Fi** (or **Ethernet**, depending on your connection)
   - Look for your TV's IP address (usually shown as "IP address" or similar, e.g., `192.168.1.42`)
   - Note this IP—you'll need it to run gtv-debloat

### Android 11+ / "Wireless debugging" (no fixed port)

Newer Google TV builds replace "Network debugging" with **Wireless debugging**, which
uses a random port and a one-time pairing step, so `--ip` (which assumes port `5555`)
won't connect directly. Pair once with `adb`, then run the tool **without** `--ip`
(it uses the already-connected device):

```bash
adb start-server
# On the TV: Developer options > Wireless debugging > "Pair device with pairing code"
# It shows an IP:PORT and a 6-digit code. Use that pairing IP:PORT here:
adb pair 192.168.0.21:PAIRING_PORT      # enter the 6-digit code when prompted
# Then connect using the IP:PORT shown on the main Wireless debugging screen:
adb connect 192.168.0.21:CONNECT_PORT
adb devices                              # confirm it shows "device" (not "offline")

python gtv_debloat.py                     # auto-targets the connected device
```

`gtv_debloat.py` with no `--ip`/`--serial` auto-picks the single connected
device, ignoring the duplicate `…_adb-tls-connect._tcp` mDNS entry that wireless
debugging registers. If auto-selection is ambiguous (several devices), pass the
exact serial from `adb devices`:

```bash
python gtv_debloat.py --serial 192.168.0.21:34793
```

Tips for flaky wireless-debugging connections (common on some MediaTek TVs):

- Keep the **Wireless debugging** screen open on the TV while working—leaving it
  can drop the connection to `offline`.
- The connect port rotates on reconnect; read the current one from that screen.
- If the first `adb pair` prints `protocol fault (couldn't read status message)`,
  the daemon had just started—re-run with a fresh pairing code, ideally inline:
  `adb pair IP:PORT CODE`.
- The tool retries once with a reconnect if a disable/enable hits `offline`.

## Usage

### Interactive Disable Menu

To launch the interactive menu and choose which apps to disable:

```bash
python gtv_debloat.py --ip 192.168.1.42
```

Replace `192.168.1.42` with your TV's actual IP address. The tool will:
1. Connect to your TV via ADB over the network
2. List all non-whitelisted installed packages—catalogued bloatware is labelled by risk level (safe/caution), uncatalogued packages are marked unknown (requiring confirmation to disable)
3. Present an interactive menu to select and disable them
4. Show a summary of disabled and skipped packages

**Note:** If your TV is connected by USB, you can omit `--ip` and the tool will use the default attached device.

### Restore Disabled Apps

To re-enable all previously disabled packages:

```bash
python gtv_debloat.py --undo --ip 192.168.1.42
```

### Custom Package Catalog

To use a different `packages.json` file:

```bash
python gtv_debloat.py --ip 192.168.1.42 --catalog /path/to/custom-packages.json
```

## Safety

**gtv-debloat is designed to be as safe as possible:**

- **Disable-only:** Uses `pm disable-user` to disable packages without uninstalling them
- **No uninstalls:** Your apps remain on disk; disabling merely hides them from the system
- **Whitelisted protection:** Critical system packages are never shown or selectable
- **Fully reversible:** You can re-enable any disabled package anytime with `--undo` or manually via `adb shell pm enable <package-name>`
- **Worst case:** Factory reset via TV Settings restores everything

Disabling certain packages (media apps, Play Store) may affect some TV features. Test carefully.

## Contributing

Community contributions to the bloatware catalog are welcome. To add or improve package entries:

1. Edit `packages.json` in your fork
2. Add or update package entries in this format:
   ```json
   {
     "package": "com.example.app",
     "description": "Example bloatware app",
     "risk": "safe"
   }
   ```
3. Risk levels: `"safe"` (no impact on core TV functionality) or `"caution"` (may affect features)
4. Submit a pull request with your changes

## Disclaimer

**Use at your own risk.** Disabling system packages can affect TV functionality. Always test on your own device first, and keep the `--undo` command handy in case something breaks. The author and contributors are not responsible for any issues caused by disabling packages on your TV.
