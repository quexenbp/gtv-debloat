import json
import subprocess
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
    "com.google.android.tv.frameworkpackagestubs",
    "android",
    "com.google.android.packageinstaller",
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
    _, out, _ = run_adb(args, serial=serial)
    pkgs = {line.split("package:", 1)[1].strip()
            for line in out.splitlines()
            if line.startswith("package:")}
    return sorted(pkgs)
