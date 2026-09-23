# gtv-debloat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A PC-side Python CLI that connects to a Google TV over ADB and reversibly disables preinstalled bloatware via an interactive menu.

**Architecture:** Single Python file (`gtv_debloat.py`) that shells out to the system `adb` binary via `subprocess`. A separate `packages.json` holds the community-editable bloat catalog. A hardcoded whitelist of critical packages is never shown, so nothing that could brick the TV is selectable. All changes use `pm disable-user --user 0` — fully reversible.

**Tech Stack:** Python 3.9+ (stdlib only: `subprocess`, `json`, `dataclasses`, `pathlib`, `argparse`), `pytest` + `unittest.mock` for tests. External runtime dependency: `adb` (Android platform-tools) on the user's PATH.

## Global Constraints

- Python 3.9+, **standard library only** at runtime — no pip dependencies. `pytest` is a dev/test dependency only.
- Never call `pm uninstall` or `adb uninstall`. Disable only, via `pm disable-user --user 0`. Reversible with `pm enable`.
- Whitelisted packages must **never** appear in any selectable list.
- Tests never invoke real `adb` — always mock `subprocess`/`run_adb`.
- All files at repo root: `gtv_debloat.py`, `packages.json`, `test_gtv_debloat.py`, `README.md`, `LICENSE`.
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

## File Structure

- `gtv_debloat.py` — the whole tool. Sections (functions in one file): ADB wrapping, catalog load/classify, disable/enable, interactive UI, `main()`.
- `packages.json` — `{ "packages": [ {package, description, risk} ] }` bloat catalog.
- `test_gtv_debloat.py` — pytest tests, `adb`/`subprocess` mocked.
- `README.md` — enable-ADB-on-Google-TV guide + usage.
- `LICENSE` — MIT.

---

### Task 1: ADB wrapper — availability, run, list packages

**Files:**
- Create: `gtv_debloat.py`
- Test: `test_gtv_debloat.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `adb_available() -> bool`
  - `run_adb(args: list[str], serial: str | None = None) -> tuple[int, str, str]` — returns `(returncode, stdout, stderr)`. Prepends `["-s", serial]` when `serial` given.
  - `list_packages(serial: str | None = None, flag: str | None = None) -> list[str]` — runs `pm list packages [flag]`, parses lines like `package:com.foo` into `["com.foo", ...]`, sorted, no dupes. `flag` is e.g. `"-s"` (system), `"-3"` (third-party), `"-d"` (disabled).

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import patch
import gtv_debloat as g

def test_list_packages_parses_and_sorts():
    fake = (0, "package:com.b\npackage:com.a\npackage:com.a\n", "")
    with patch.object(g, "run_adb", return_value=fake):
        assert g.list_packages() == ["com.a", "com.b"]

def test_list_packages_forwards_flag_and_serial():
    with patch.object(g, "run_adb", return_value=(0, "", "")) as m:
        g.list_packages(serial="1.2.3.4:5555", flag="-s")
        m.assert_called_once_with(["shell", "pm", "list", "packages", "-s"],
                                  serial="1.2.3.4:5555")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_gtv_debloat.py -v`
Expected: FAIL — `module 'gtv_debloat' has no attribute 'list_packages'`.

- [ ] **Step 3: Write minimal implementation**

```python
import subprocess

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_gtv_debloat.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add gtv_debloat.py test_gtv_debloat.py
git commit -m "feat: add adb wrapper (available, run, list packages)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Catalog + whitelist classification

**Files:**
- Create: `packages.json`
- Modify: `gtv_debloat.py`
- Test: `test_gtv_debloat.py`

**Interfaces:**
- Consumes: `list_packages` (Task 1) — not directly, receives package name lists as args.
- Produces:
  - `Pkg` dataclass: `Pkg(package: str, description: str, risk: str)` where `risk ∈ {"safe", "caution", "unknown"}`.
  - `WHITELIST_PREFIXES: tuple[str, ...]` — critical package prefixes.
  - `is_protected(package: str) -> bool` — True if `package` starts with any whitelist prefix.
  - `load_catalog(path="packages.json") -> dict[str, dict]` — returns `{package: {"description": str, "risk": str}}`.
  - `selectable_packages(installed: list[str], catalog: dict) -> list[Pkg]` — drops protected packages entirely; maps each remaining package to a `Pkg` using catalog info, or `risk="unknown"` / `description=""` when uncatalogued.

- [ ] **Step 1: Write the failing test**

```python
def test_protected_packages_never_selectable():
    installed = ["com.android.systemui", "com.google.android.gsf",
                 "com.arcelik.bloat", "com.random.app"]
    catalog = {"com.arcelik.bloat": {"description": "demo", "risk": "safe"}}
    result = g.selectable_packages(installed, catalog)
    names = [p.package for p in result]
    assert "com.android.systemui" not in names
    assert "com.google.android.gsf" not in names
    assert "com.arcelik.bloat" in names

def test_classify_known_vs_unknown():
    installed = ["com.arcelik.bloat", "com.random.app"]
    catalog = {"com.arcelik.bloat": {"description": "demo", "risk": "safe"}}
    by_name = {p.package: p for p in g.selectable_packages(installed, catalog)}
    assert by_name["com.arcelik.bloat"].risk == "safe"
    assert by_name["com.arcelik.bloat"].description == "demo"
    assert by_name["com.random.app"].risk == "unknown"

def test_load_catalog_reads_json(tmp_path):
    f = tmp_path / "packages.json"
    f.write_text('{"packages":[{"package":"com.x","description":"d","risk":"caution"}]}')
    cat = g.load_catalog(f)
    assert cat["com.x"] == {"description": "d", "risk": "caution"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_gtv_debloat.py -v`
Expected: FAIL — `selectable_packages` / `load_catalog` not defined.

- [ ] **Step 3: Write minimal implementation**

Add to `gtv_debloat.py`:

```python
import json
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
```

Create `packages.json` (starter Arçelik/Google TV baseline — grown via PRs):

```json
{
  "packages": [
    {"package": "com.google.android.youtube.tvkids", "description": "YouTube Kids for TV", "risk": "safe"},
    {"package": "com.google.android.videos", "description": "Google TV / Play Movies", "risk": "caution"},
    {"package": "com.google.android.play.games", "description": "Google Play Games", "risk": "safe"},
    {"package": "com.google.android.music", "description": "Play Music (legacy)", "risk": "safe"},
    {"package": "com.netflix.ninja", "description": "Netflix (preinstalled)", "risk": "caution"},
    {"package": "com.amazon.amazonvideo.livingroom", "description": "Amazon Prime Video (preinstalled)", "risk": "caution"}
  ]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_gtv_debloat.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add gtv_debloat.py packages.json test_gtv_debloat.py
git commit -m "feat: add bloat catalog and whitelist classification

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Disable / enable with summary

**Files:**
- Modify: `gtv_debloat.py`
- Test: `test_gtv_debloat.py`

**Interfaces:**
- Consumes: `run_adb` (Task 1), `is_protected` (Task 2).
- Produces:
  - `disable_packages(packages: list[str], serial=None) -> dict` — for each: refuse if `is_protected` (add to `"skipped"`), else `run_adb(["shell", "pm", "disable-user", "--user", "0", pkg])`; rc==0 → `"disabled"`, else `"skipped"`. Returns `{"disabled": [...], "skipped": [...]}`.
  - `enable_packages(packages: list[str], serial=None) -> dict` — same shape, runs `pm enable`.

- [ ] **Step 1: Write the failing test**

```python
def test_disable_refuses_protected_and_reports_summary():
    calls = []
    def fake_run(args, serial=None):
        calls.append(args)
        return (0, "", "")
    with patch.object(g, "run_adb", side_effect=fake_run):
        res = g.disable_packages(["com.arcelik.bloat", "com.android.systemui"])
    assert res["disabled"] == ["com.arcelik.bloat"]
    assert res["skipped"] == ["com.android.systemui"]
    # protected package must not have hit adb
    assert all("com.android.systemui" not in a for a in calls)

def test_disable_marks_failed_as_skipped():
    def fake_run(args, serial=None):
        return (1, "", "Failure")
    with patch.object(g, "run_adb", side_effect=fake_run):
        res = g.disable_packages(["com.x"])
    assert res["disabled"] == []
    assert res["skipped"] == ["com.x"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_gtv_debloat.py -v`
Expected: FAIL — `disable_packages` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_gtv_debloat.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add gtv_debloat.py test_gtv_debloat.py
git commit -m "feat: add reversible disable/enable with summary

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Connection helper + interactive UI + main()

**Files:**
- Modify: `gtv_debloat.py`
- Test: `test_gtv_debloat.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `ensure_connected(ip: str | None = None) -> str | None` — if `ip` given, `run_adb(["connect", f"{ip}:5555"])`; returns the serial string `f"{ip}:5555"` on success (stdout contains "connected"), else `None`. With no `ip`, returns `None` (caller falls back to default USB device).
  - `parse_selection(raw: str, count: int) -> list[int]` — parses user input like `"1 3 5"` or `"1,3,5"` into a sorted list of unique 0-based indices within `range(count)`; ignores out-of-range/garbage tokens.
  - `main(argv=None) -> int` — argparse (`--ip`, `--undo`, `--catalog`), wires the flow, prints menu, returns process exit code. Not unit-tested beyond smoke; logic lives in the pure helpers above.

- [ ] **Step 1: Write the failing test**

```python
def test_parse_selection_handles_commas_spaces_and_bounds():
    assert g.parse_selection("1 3 3 5", 4) == [1, 3]      # 5 out of range dropped
    assert g.parse_selection("0,2", 3) == [0, 2]
    assert g.parse_selection("x 1 -2", 3) == [1]          # garbage/negative dropped
    assert g.parse_selection("", 3) == []

def test_ensure_connected_returns_serial_on_success():
    with patch.object(g, "run_adb", return_value=(0, "connected to 1.2.3.4:5555", "")):
        assert g.ensure_connected("1.2.3.4") == "1.2.3.4:5555"

def test_ensure_connected_returns_none_on_failure():
    with patch.object(g, "run_adb", return_value=(1, "", "cannot connect")):
        assert g.ensure_connected("1.2.3.4") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_gtv_debloat.py -v`
Expected: FAIL — `parse_selection` / `ensure_connected` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
import argparse
import sys

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_gtv_debloat.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add gtv_debloat.py test_gtv_debloat.py
git commit -m "feat: add connection, selection parsing, and interactive main

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: README + LICENSE

**Files:**
- Create: `README.md`, `LICENSE`

**Interfaces:** none (docs).

- [ ] **Step 1: Write `LICENSE`**

MIT license text, copyright holder `emrecan.bilgili`, year 2026.

- [ ] **Step 2: Write `README.md`**

Must contain, in order:
1. One-paragraph what/why (reversible bloatware disabler, no root).
2. **Requirements:** Python 3.9+, `adb` (platform-tools) on PATH.
3. **Enable ADB on Google TV** (step-by-step): Settings > System > About > tap "Android TV OS build" / "Build" 7×; back to Settings > System > Developer options > enable **USB debugging** and **Network debugging**; note the TV's IP (Settings > Network & Internet).
4. **Usage:**
   ```bash
   python gtv_debloat.py --ip 192.168.1.42     # disable menu
   python gtv_debloat.py --undo --ip 192.168.1.42   # restore
   ```
5. **Safety:** disable-only (`pm disable-user`), never uninstalls, whitelisted system packages hidden, everything reversible; worst case `adb shell pm enable <pkg>` or factory reset.
6. **Contributing:** add devices/packages to `packages.json` via PR; explain the `{package, description, risk}` shape.
7. Disclaimer: use at own risk, disabling media/store apps may affect features.

- [ ] **Step 3: Verify tests still pass**

Run: `pytest test_gtv_debloat.py -v`
Expected: PASS (docs change nothing).

- [ ] **Step 4: Commit**

```bash
git add README.md LICENSE
git commit -m "docs: add README (enable-ADB guide + usage) and MIT LICENSE

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Connect over network ADB → Task 4 `ensure_connected`. ✓
- List installed packages → Task 1 `list_packages`. ✓
- Flag known bloatware → Task 2 catalog + `selectable_packages`. ✓
- Disable selected via `pm disable-user` → Task 3. ✓
- Undo/enable → Task 3 `enable_packages` + Task 4 `--undo`. ✓
- Whitelist safety (never displayed/selectable) → Task 2 `is_protected` + selectable filter, Task 3 double-guard. ✓
- Unknown-package extra warning → Task 4 `main`. ✓
- Error handling (adb missing, connect fail, per-package skip+summary) → Task 4 + Task 3. ✓
- Interactive menu → Task 4. ✓
- Catalog as separate community-editable file → Task 2 `packages.json`. ✓
- Tests with mocked adb; whitelist-never-selectable minimum check → Task 2 test. ✓
- README with enable-ADB guide → Task 5. ✓

**Placeholder scan:** No TBD/TODO; every code step has real code. ✓

**Type consistency:** `run_adb` returns `(rc, out, err)` everywhere; `Pkg(package, description, risk)` consistent; `serial` param name consistent; `{"disabled":[], "skipped":[]}` summary shape consistent across disable/enable. ✓
