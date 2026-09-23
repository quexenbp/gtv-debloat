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
