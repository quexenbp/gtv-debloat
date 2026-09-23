import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

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
                           "risk": e.get("risk", "safe")}
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

def _apply(action, packages, serial):
    disabled, skipped = [], []
    for pkg in packages:
        if action == "disable-user" and is_protected(pkg):
            skipped.append(pkg)
            continue
        args = ["shell", "pm", action]
        if action == "disable-user":
            args += ["--user", "0"]
        args.append(pkg)
        rc, _, _ = run_adb(args, serial=serial)
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
    parser.add_argument("--ip", help="TV IP for network ADB (adb connect IP:5555)")
    parser.add_argument("--undo", action="store_true", help="re-enable currently disabled packages")
    parser.add_argument("--catalog", default="packages.json", help="path to bloat catalog")
    args = parser.parse_args(argv)

    if not adb_available():
        print("adb not found. Install Android platform-tools: "
              "https://developer.android.com/tools/releases/platform-tools")
        return 1

    serial = ensure_connected(args.ip)
    if args.ip and serial is None:
        print("Could not connect. On the TV enable Developer options + "
              "Network debugging (Settings > System > About > tap Build 7x, "
              "then Settings > System > Developer options).")
        return 1

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
    print("Undo anytime: python gtv_debloat.py --undo" + (f" --ip {args.ip}" if args.ip else ""))
    return 0

if __name__ == "__main__":
    sys.exit(main())
