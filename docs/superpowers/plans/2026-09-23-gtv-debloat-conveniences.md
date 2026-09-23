# gtv-debloat Conveniences Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax. Follow AGENTS.md: one fresh agent per task, model haiku→sonnet→opus by confidence.

**Goal:** Remove ADB-connection friction and add quality-of-life features to gtv-debloat (`--pair`, `--all-safe`, `--version`, `run.bat`, issue templates, README).

**Architecture:** All logic stays in single-file `gtv_debloat.py`; new helpers + flags. New files: `run.bat`, `.github/ISSUE_TEMPLATE/*`.

**Tech Stack:** Python 3.9+ stdlib only; pytest (dev) with mocked adb.

## Global Constraints

- Python 3.9+, standard library only at runtime. pytest dev-only.
- Never `pm uninstall`/`adb uninstall`; disable via `pm disable-user --user 0`.
- Whitelisted packages never selectable/disabled; `--all-safe` only targets catalogued `risk=="safe"`.
- Tests mock adb/subprocess — no real device.
- Interpreter (the `python` command is a broken stub): `C:\Users\rogsr\AppData\Local\Programs\Python\Python312\python.exe`.
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

### Task 1: `--version` flag

**Files:** Modify `gtv_debloat.py`; Test `test_gtv_debloat.py`.

**Interfaces:** Produces module `__version__ = "0.1.0"`; `main(["--version"])` prints it and returns 0 without any adb call.

- [ ] **Step 1: Failing test**
```python
def test_version_prints_and_exits(capsys):
    rc = g.main(["--version"])
    assert rc == 0
    assert "0.1.0" in capsys.readouterr().out
```
- [ ] **Step 2: Run — expect FAIL** (`--version` unrecognized / no `__version__`).
Run: `pytest test_gtv_debloat.py::test_version_prints_and_exits -v`
- [ ] **Step 3: Implement**
Add near top of `gtv_debloat.py` (after imports): `__version__ = "0.1.0"`.
In `main`, add argument and handle it FIRST (before adb check):
```python
    parser.add_argument("--version", action="store_true", help="print version and exit")
    args = parser.parse_args(argv)

    if args.version:
        print(f"gtv-debloat {__version__}")
        return 0
```
(Place the `--version` add-argument with the others; place the `if args.version` block immediately after `args = parser.parse_args(argv)`, before the `adb_available()` check.)
- [ ] **Step 4: Run — expect PASS** (full file).
- [ ] **Step 5: Commit** `feat: add --version flag`.

---

### Task 2: `--all-safe` bulk disable

**Files:** Modify `gtv_debloat.py`; Test `test_gtv_debloat.py`.

**Interfaces:** Consumes `load_catalog`, `list_packages`, `is_protected`, `disable_packages`. Produces `safe_targets(installed, catalog) -> list[str]` returning installed packages whose catalog risk is `"safe"` and which are not protected; and an `--all-safe` path in `main`.

- [ ] **Step 1: Failing test**
```python
def test_safe_targets_only_catalogued_safe_and_unprotected():
    installed = ["com.a", "com.b", "com.c", "com.android.systemui"]
    catalog = {"com.a": {"description": "", "risk": "safe"},
               "com.b": {"description": "", "risk": "caution"},
               "com.android.systemui": {"description": "", "risk": "safe"}}
    assert g.safe_targets(installed, catalog) == ["com.a"]

def test_main_all_safe_disables_safe_set(tmp_path):
    cat = tmp_path / "packages.json"
    cat.write_text('{"packages":[{"package":"com.a","description":"","risk":"safe"},'
                   '{"package":"com.b","description":"","risk":"caution"}]}')
    with patch.object(g, "adb_available", return_value=True), \
         patch.object(g, "resolve_serial", return_value="1.2.3.4:5555"), \
         patch.object(g, "list_packages", return_value=["com.a", "com.b"]), \
         patch.object(g, "disable_packages", return_value={"disabled": ["com.a"], "skipped": []}) as md:
        rc = g.main(["--all-safe", "--catalog", str(cat)])
    assert rc == 0
    md.assert_called_once_with(["com.a"], serial="1.2.3.4:5555")
```
- [ ] **Step 2: Run — expect FAIL** (`safe_targets` undefined).
- [ ] **Step 3: Implement**
Add helper (near `selectable_packages`):
```python
def safe_targets(installed, catalog):
    return [pkg for pkg in installed
            if not is_protected(pkg)
            and catalog.get(pkg, {}).get("risk") == "safe"]
```
Add flag: `parser.add_argument("--all-safe", action="store_true", help="disable every catalogued SAFE package")`.
In `main`, after `serial` is resolved and before the interactive default menu (and not under `--undo`), add:
```python
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
```
(argparse turns `--all-safe` into `args.all_safe`.)
- [ ] **Step 4: Run — expect PASS** (full file).
- [ ] **Step 5: Commit** `feat: add --all-safe bulk disable`.

---

### Task 3: `--pair` guided pairing wizard

**Files:** Modify `gtv_debloat.py`; Test `test_gtv_debloat.py`.

**Interfaces:** Consumes `run_adb`, `ensure_connected`/`resolve_serial`. Produces `pair_device(pair_endpoint, code) -> bool` (runs `adb pair <endpoint> <code>`; on `protocol fault` runs `adb start-server` then retries once; returns True iff output contains "successfully paired"); and a `--pair` prompt flow in `main`.

- [ ] **Step 1: Failing test**
```python
def test_pair_device_success():
    with patch.object(g, "run_adb", return_value=(0, "Successfully paired to 1.2.3.4:5", "")) as m:
        assert g.pair_device("1.2.3.4:5", "123456") is True
        m.assert_called_once_with(["pair", "1.2.3.4:5", "123456"])

def test_pair_device_retries_on_protocol_fault():
    seq = iter([(1, "", "protocol fault (couldn't read status message)"),
                (0, "", ""),                       # start-server
                (0, "Successfully paired", "")])    # retry pair
    with patch.object(g, "run_adb", side_effect=lambda *a, **k: next(seq)):
        assert g.pair_device("1.2.3.4:5", "123456") is True

def test_pair_device_failure():
    with patch.object(g, "run_adb", return_value=(1, "", "failed")):
        assert g.pair_device("1.2.3.4:5", "000000") is False
```
- [ ] **Step 2: Run — expect FAIL** (`pair_device` undefined).
- [ ] **Step 3: Implement**
```python
def pair_device(pair_endpoint, code):
    rc, out, err = run_adb(["pair", pair_endpoint, code])
    if "protocol fault" in (out + err).lower():
        run_adb(["start-server"])
        rc, out, err = run_adb(["pair", pair_endpoint, code])
    return "successfully paired" in (out + err).lower()
```
Add flag `parser.add_argument("--pair", action="store_true", help="guided Wireless debugging pairing")`.
In `main`, immediately after the `adb_available()` check and before serial resolution, add:
```python
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
```
(This runs before serial resolution so the just-connected `ce` is used. Keep the existing serial-resolution block after it unchanged.)
- [ ] **Step 4: Run — expect PASS** (full file).
- [ ] **Step 5: Commit** `feat: add --pair guided wireless-debugging wizard`.

---

### Task 4: run.bat, issue templates, README

**Files:** Create `run.bat`, `.github/ISSUE_TEMPLATE/package-suggestion.md`, `.github/ISSUE_TEMPLATE/bricking-report.md`; Modify `README.md`.

**Interfaces:** none (launcher + docs).

- [ ] **Step 1: Create `run.bat`**
```bat
@echo off
setlocal
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY set "PY=python"
%PY% "%~dp0gtv_debloat.py" %*
pause
```
- [ ] **Step 2: Create `.github/ISSUE_TEMPLATE/package-suggestion.md`**
Front-matter (`name: Package suggestion`, `about: Suggest catalog entries for your TV`, `title: "packages: <brand/model>"`, `labels: catalog`) then fields: TV brand/model, Android TV OS version, the package name(s), proposed risk (safe/caution) and why, how you verified safe ones.
- [ ] **Step 3: Create `.github/ISSUE_TEMPLATE/bricking-report.md`**
Front-matter (`name: Bricking risk`, `about: A selectable package broke a core feature`, `title: "bricking risk: <package>"`, `labels: bug, whitelist`) then fields: package, TV brand/model + OS version, what broke, whether `--undo` recovered it.
- [ ] **Step 4: Update `README.md`**
Add a "Quick start" section near the top (double-click `run.bat`, or `python gtv_debloat.py --pair` to connect, then pick packages; `--all-safe` to bulk-clean; `--undo` to restore). Document `--pair`, `--all-safe`, `--version`, and `run.bat` in Usage.
- [ ] **Step 5: Verify tests still pass** (`pytest test_gtv_debloat.py -v`) — docs/bat change nothing.
- [ ] **Step 6: Commit** `feat: add run.bat launcher, issue templates, README quick start`.

---

## Self-Review

- Spec coverage: `--pair` (T3), `run.bat` (T4), `--all-safe` (T2), `--version`+templates+README (T1/T4). ✓
- No placeholders: every code step has real code. ✓
- Type consistency: `disable_packages(list, serial=)` call shape matches existing; `safe_targets`/`pair_device` signatures used consistently. ✓
- Safety: `--all-safe` filters via catalog `safe` + `is_protected` guard intact; no uninstall introduced. ✓
