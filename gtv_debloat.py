import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

__version__ = "0.1.0"

_IP_PORT = re.compile(r"^\d+\.\d+\.\d+\.\d+:\d+$")

@dataclass
class Pkg:
    package: str
    description: str
    risk: str  # "safe" | "caution" | "unknown"

WHITELIST_PREFIXES = (
    "com.android.",
    "com.google.android.gsf",
    "com.google.android.gms",
    "com.google.android.tvlauncher",
    "com.google.android.apps.tv.launcherx",  # Google TV home launcher (newer)
    "com.google.android.tv.frameworkpackagestubs",
    "android",
    "com.google.android.packageinstaller",
    "com.google.android.permissioncontroller",  # runtime permission UI
    "com.google.android.overlay.",              # framework RRO overlays
    "com.google.android.modulemetadata",        # mainline module metadata
    "com.google.android.ext.services",          # framework ext services
    "com.google.android.ext.shared",
    "com.google.android.onetimeinitializer",
    "com.google.android.inputmethod.latin",     # only keyboard: no text input = unusable
    "com.google.android.webview",               # many apps/settings need WebView
    "com.mediatek.tv.service",                  # panel/tuner core (covers .rro)
    "com.mediatek.tvinput",                     # HDMI/tuner input source
    "com.google.android.tv.settings",           # TV Settings app + its RRO overlays
)

def is_protected(package):
    return any(package == p or package.startswith(p) for p in WHITELIST_PREFIXES)

def load_catalog(path="packages.json"):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {e["package"]: {"description": e.get("description", ""),
                           "risk": e.get("risk", "caution")}
            for e in data.get("packages", [])}

def selectable_packages(installed, catalog):
    out = []
    for pkg in installed:
        if is_protected(pkg):
            continue
        info = catalog.get(pkg)
        if info:
            out.append(Pkg(pkg, info["description"], info["risk"]))
        else:
            out.append(Pkg(pkg, "", "unknown"))
    return out

def safe_targets(installed, catalog):
    return [pkg for pkg in installed
            if not is_protected(pkg)
            and catalog.get(pkg, {}).get("risk") == "safe"]

def adb_available() -> bool:
    try:
        subprocess.run(["adb", "version"], capture_output=True, text=True)
        return True
    except FileNotFoundError:
        return False

def run_adb(args, serial=None):
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += args
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

def pair_device(pair_endpoint, code):
    rc, out, err = run_adb(["pair", pair_endpoint, code])
    if "protocol fault" in (out + err).lower():
        run_adb(["start-server"])
        rc, out, err = run_adb(["pair", pair_endpoint, code])
    return "successfully paired" in (out + err).lower()

def list_packages(serial=None, flag=None):
    args = ["shell", "pm", "list", "packages"]
    if flag:
        args.append(flag)
    rc, out, err = run_adb(args, serial=serial)
    if rc != 0:
        print(f"warning: adb read failed: {err.strip()}", file=sys.stderr)
    pkgs = {line.split("package:", 1)[1].strip()
            for line in out.splitlines()
            if line.startswith("package:")}
    return sorted(pkgs)

def list_devices():
    """Parse `adb devices` into [(serial, state), ...]."""
    _, out, _ = run_adb(["devices"])
    devs = []
    for line in out.splitlines()[1:]:
        if "\t" in line:
            serial, state = line.split("\t", 1)
            devs.append((serial.strip(), state.strip()))
    return devs

def resolve_serial(explicit=None):
    """Pick which device adb should target.

    Priority: explicit serial > the single online IP:port device > the single
    online device > None (let adb use its default). Wireless debugging often
    registers a duplicate mDNS entry (…_adb-tls-connect._tcp) alongside the
    real IP:port one, so an IP:port device is preferred to disambiguate.
    """
    if explicit:
        return explicit
    online = [s for s, st in list_devices() if st == "device"]
    ipish = [s for s in online if _IP_PORT.match(s)]
    if len(ipish) == 1:
        return ipish[0]
    if len(online) == 1:
        return online[0]
    return None

def _run_pm(action, pkg, serial):
    args = ["shell", "pm", action]
    if action == "disable-user":
        args += ["--user", "0"]
    args.append(pkg)
    rc, out, err = run_adb(args, serial=serial)
    if rc != 0 and "offline" in (out + err).lower():
        # ponytail: one blind reconnect + retry. Rotating wireless-debugging
        # ports can still require a manual re-pair, which no retry can fix.
        run_adb(["reconnect", "offline"])
        if serial:
            run_adb(["connect", serial])
        rc, out, err = run_adb(args, serial=serial)
    return rc

def _apply(action, packages, serial):
    disabled, skipped = [], []
    for pkg in packages:
        if action == "disable-user" and is_protected(pkg):
            skipped.append(pkg)
            continue
        rc = _run_pm(action, pkg, serial)
        (disabled if rc == 0 else skipped).append(pkg)
    return {"disabled": disabled, "skipped": skipped}

def disable_packages(packages, serial=None):
    return _apply("disable-user", packages, serial)

def enable_packages(packages, serial=None):
    return _apply("enable", packages, serial)

def ensure_connected(ip=None):
    if not ip:
        return None
    serial = f"{ip}:5555"
    rc, out, _ = run_adb(["connect", serial])
    return serial if rc == 0 and "connected" in out.lower() else None

def parse_selection(raw, count):
    idx = set()
    for tok in raw.replace(",", " ").split():
        try:
            n = int(tok)
        except ValueError:
            continue
        if 0 <= n < count:
            idx.add(n)
    return sorted(idx)

def _print_menu(pkgs):
    for i, p in enumerate(pkgs):
        tag = p.risk.upper()
        desc = p.description or "(uncatalogued — unknown, disable at your own risk)"
        print(f"[{i}] {p.package}  <{tag}>  {desc}")

def main(argv=None):
    parser = argparse.ArgumentParser(description="Reversibly disable Google TV bloatware over ADB.")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    parser.add_argument("--ip", help="TV IP for network ADB (adb connect IP:5555)")
    parser.add_argument("--serial", help="exact adb device serial to target "
                        "(e.g. 192.168.0.21:34793); use with wireless debugging")
    parser.add_argument("--undo", action="store_true", help="re-enable currently disabled packages")
    parser.add_argument("--all-safe", action="store_true", help="disable every catalogued SAFE package")
    parser.add_argument("--pair", action="store_true", help="guided Wireless debugging pairing")
    parser.add_argument("--catalog", default="packages.json", help="path to bloat catalog")
    args = parser.parse_args(argv)

    if args.version:
        print(f"gtv-debloat {__version__}")
        return 0

    if not adb_available():
        print("adb not found. Install Android platform-tools: "
              "https://developer.android.com/tools/releases/platform-tools")
        return 1

    if args.pair:
        print("On the TV: Developer options > Wireless debugging > "
              "'Pair device with pairing code'.")
        pe = input("Pairing IP:PORT (from the pairing popup): ").strip()
        code = input("6-digit pairing code: ").strip()
        if not pair_device(pe, code):
            print("Pairing failed. Re-open the popup for a fresh code and retry.")
            return 1
        print("Paired.")
        ce = input("Connect IP:PORT (from the main Wireless debugging screen): ").strip()
        rc, out, _ = run_adb(["connect", ce])
        if not (rc == 0 and "connected" in out.lower()):
            print("Connect failed. Check the port on the TV screen and retry.")
            return 1
        print("Connected. Continuing...")
        args.serial = args.serial or ce

    serial = args.serial
    if serial is None and args.ip:
        serial = ensure_connected(args.ip)
        if serial is None:
            print("Could not connect. On the TV enable Developer options + "
                  "Network debugging (Settings > System > About > tap Build 7x, "
                  "then Settings > System > Developer options). For Android 11+ "
                  "Wireless debugging, pair manually and pass --serial IP:PORT.")
            return 1
    if serial is None:
        serial = resolve_serial()

    if args.undo:
        disabled = list_packages(serial=serial, flag="-d")
        if not disabled:
            print("No disabled packages to restore.")
            return 0
        for i, p in enumerate(disabled):
            print(f"[{i}] {p}")
        sel = parse_selection(input("Re-enable which? (numbers, blank=all): "),
                              len(disabled))
        targets = disabled if not sel else [disabled[i] for i in sel]
        res = enable_packages(targets, serial=serial)
        print(f"Re-enabled {len(res['disabled'])}, skipped {len(res['skipped'])}.")
        return 0

    if args.all_safe:
        catalog = load_catalog(args.catalog)
        installed = list_packages(serial=serial)
        targets = safe_targets(installed, catalog)
        if not targets:
            print("No catalogued SAFE packages found on device.")
            return 0
        print("Disabling SAFE packages:", ", ".join(targets))
        res = disable_packages(targets, serial=serial)
        print(f"Disabled {len(res['disabled'])}, skipped {len(res['skipped'])}.")
        return 0

    catalog = load_catalog(args.catalog)
    installed = list_packages(serial=serial)
    pkgs = selectable_packages(installed, catalog)
    _print_menu(pkgs)
    sel = parse_selection(input("Disable which? (e.g. 0 2 5): "), len(pkgs))
    if not sel:
        print("Nothing selected.")
        return 0
    targets = [pkgs[i] for i in sel]
    unknown = [p.package for p in targets if p.risk == "unknown"]
    if unknown:
        print("WARNING: uncatalogued packages selected:", ", ".join(unknown))
        if input("Type 'yes' to proceed: ").strip().lower() != "yes":
            print("Aborted.")
            return 0
    res = disable_packages([p.package for p in targets], serial=serial)
    print(f"Disabled {len(res['disabled'])}, skipped {len(res['skipped'])}.")
    hint = "Undo anytime: python gtv_debloat.py --undo"
    if args.serial:
        hint += f" --serial {args.serial}"
    elif args.ip:
        hint += f" --ip {args.ip}"
    print(hint)
    return 0

if __name__ == "__main__":
    sys.exit(main())
