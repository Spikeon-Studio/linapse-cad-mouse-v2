import sys
import os
import urllib.request
import json
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from . import state

def compare_versions(v1, v2):
    v1 = v1.lstrip('v')
    v2 = v2.lstrip('v')
    parts1 = [int(p) for p in v1.split('.') if p.isdigit()]
    parts2 = [int(p) for p in v2.split('.') if p.isdigit()]
    for i in range(max(len(parts1), len(parts2))):
        p1 = parts1[i] if i < len(parts1) else 0
        p2 = parts2[i] if i < len(parts2) else 0
        if p1 < p2:
            return -1
        elif p1 > p2:
            return 1
    return 0

def check_for_updates(quiet=False):
    if state.software_update_status in ("checking", "downloading"):
        return
    state.software_update_status = "checking"
    state.broadcast_from_thread("SOFTWARE_UPDATE:checking")
    headers = {"User-Agent": "Linapse-Service"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/spikeon/linapse-cad-mouse-v2/releases/latest",
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            tag_name = data.get("tag_name", "")
            if not tag_name:
                raise ValueError("No tag name in release data")
            
            if compare_versions(tag_name, state.service_version) > 0:
                state.latest_software_version = tag_name.lstrip('v')
                state.software_update_status = "available"
                state.software_update_url = None
                
                # Find platform-specific asset
                for asset in data.get("assets", []):
                    name = asset.get("name", "")
                    if sys.platform == "win32" and name.endswith(".exe"):
                        state.software_update_url = asset.get("browser_download_url")
                        break
                    elif sys.platform == "darwin" and name.endswith(".pkg"):
                        state.software_update_url = asset.get("browser_download_url")
                        break
                
                # Default fallback
                if not state.software_update_url:
                    state.software_update_url = data.get("zipball_url") or data.get("html_url")
                
                state.broadcast_from_thread(f"SOFTWARE_UPDATE:available:{state.latest_software_version}:{state.software_update_url}")
                if not quiet:
                    print(f"[updater] New version available: {tag_name}")
            else:
                state.software_update_status = "idle"
                state.broadcast_from_thread("SOFTWARE_UPDATE:idle")
                if not quiet:
                    print("[updater] Service is up to date.")
    except Exception as e:
        # Fallback to fetching raw VERSION file directly from GitHub (never rate-limited)
        try:
            if not quiet:
                print(f"[updater] Primary check failed ({e}). Trying fallback raw VERSION check...")
            fallback_req = urllib.request.Request(
                "https://raw.githubusercontent.com/spikeon/linapse-cad-mouse-v2/main/VERSION",
                headers={"User-Agent": "Linapse-Service"}
            )
            with urllib.request.urlopen(fallback_req, timeout=10) as response:
                raw_ver = response.read().decode().strip()
                if not raw_ver:
                    raise ValueError("Empty version file")
                
                tag_name = "v" + raw_ver
                if compare_versions(tag_name, state.service_version) > 0:
                    state.latest_software_version = raw_ver
                    state.software_update_status = "available"
                    state.software_update_url = f"https://github.com/spikeon/linapse-cad-mouse-v2/releases/tag/{tag_name}"
                    
                    state.broadcast_from_thread(f"SOFTWARE_UPDATE:available:{state.latest_software_version}:{state.software_update_url}")
                    if not quiet:
                        print(f"[updater] New version available (fallback): {tag_name}")
                else:
                    state.software_update_status = "idle"
                    state.broadcast_from_thread("SOFTWARE_UPDATE:idle")
                    if not quiet:
                        print("[updater] Service is up to date (fallback).")
        except Exception as fallback_err:
            state.software_update_status = "failed"
            state.broadcast_from_thread(f"SOFTWARE_UPDATE:failed:Check error: {str(e)}")
            print(f"[updater] Update check failed: {e} (fallback: {fallback_err})")

def download_and_install_update():
    if state.software_update_status != "available" or not state.software_update_url:
        print("[updater] No update available or URL missing")
        return
    
    state.software_update_status = "downloading"
    state.broadcast_from_thread("SOFTWARE_UPDATE:downloading:0")
    
    def run_download():
        try:
            url = state.software_update_url
            print(f"[updater] Starting download from {url}")
            
            repo_root = Path(__file__).resolve().parent.parent.parent
            is_git_repo = repo_root.joinpath(".git").exists()
            
            if sys.platform not in ("win32", "darwin") and is_git_repo:
                state.broadcast_from_thread("SOFTWARE_UPDATE:downloading:50")
                print(f"[updater] Git repository detected at {repo_root}. Running git pull...")
                res = subprocess.run(["git", "pull"], cwd=str(repo_root), capture_output=True, text=True)
                if res.returncode == 0:
                    state.broadcast_from_thread("SOFTWARE_UPDATE:downloading:90")
                    print("[updater] Git pull successful. Syncing version...")
                    subprocess.run([sys.executable, "scripts/sync_version.py"], cwd=str(repo_root))
                    state.software_update_status = "ready"
                    state.broadcast_from_thread("SOFTWARE_UPDATE:ready")
                    time.sleep(1)
                    print("[updater] Restarting systemd service...")
                    subprocess.Popen(["systemctl", "--user", "restart", "linapse-service"])
                    sys.exit(0)
                else:
                    raise Exception(f"Git pull failed: {res.stderr}")
            
            # Standard binary download
            req = urllib.request.Request(url, headers={"User-Agent": "Linapse-Service"})
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                suffix = ".exe" if sys.platform == "win32" else (".pkg" if sys.platform == "darwin" else ".tar.gz")
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    temp_file_path = tmp_file.name
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        tmp_file.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            state.broadcast_from_thread(f"SOFTWARE_UPDATE:downloading:{percent}")
            
            print(f"[updater] Download complete: {temp_file_path}")
            state.software_update_status = "ready"
            state.broadcast_from_thread("SOFTWARE_UPDATE:ready")
            time.sleep(1.0)
            
            if sys.platform == "win32":
                print("[updater] Launching Windows setup...")
                subprocess.Popen([temp_file_path], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS)
                sys.exit(0)
            elif sys.platform == "darwin":
                print("[updater] Launching macOS installer...")
                subprocess.Popen(["open", temp_file_path])
                sys.exit(0)
            else:
                import shutil
                import tarfile
                
                # Copy to ~/Downloads
                downloads_dir = Path.home() / "Downloads"
                downloads_dir.mkdir(exist_ok=True)
                dest_path = downloads_dir / f"linapse-cad-mouse-v2-{state.latest_software_version}.tar.gz"
                shutil.copy(temp_file_path, dest_path)
                print(f"[updater] Package copied to {dest_path}")
                
                # Extract to ~/Downloads/linapse-cad-mouse-v2-<version>
                extract_dir = downloads_dir / f"linapse-cad-mouse-v2-{state.latest_software_version}"
                if extract_dir.exists():
                    shutil.rmtree(extract_dir)
                extract_dir.mkdir(exist_ok=True)
                
                print(f"[updater] Extracting package to {extract_dir}...")
                with tarfile.open(temp_file_path, "r:gz") as tar:
                    tar.extractall(path=extract_dir)
                
                # Find setup.sh
                setup_sh_path = None
                for p in extract_dir.rglob("setup.sh"):
                    setup_sh_path = p
                    break
                
                if setup_sh_path:
                    setup_sh_path.chmod(setup_sh_path.stat().st_mode | 0o111)
                    state.downloaded_installer_path = str(setup_sh_path)
                    print(f"[updater] Found installer setup.sh at {state.downloaded_installer_path}")
                else:
                    state.downloaded_installer_path = None
                    print("[updater] setup.sh not found in extracted files")
                
                state.software_update_status = "manual_linux"
                state.broadcast_from_thread(f"SOFTWARE_UPDATE:manual_linux:{dest_path}")
        except Exception as e:
            state.software_update_status = "failed"
            state.broadcast_from_thread(f"SOFTWARE_UPDATE:failed:{str(e)}")
            print(f"[updater] Download/install failed: {e}")

    threading.Thread(target=run_download, daemon=True).start()

def run_downloaded_installer():
    if not state.downloaded_installer_path:
        print("[updater] No installer setup.sh found.")
        return
    
    import shutil
    import subprocess
    from pathlib import Path
    
    setup_sh = Path(state.downloaded_installer_path)
    cwd = str(setup_sh.parent)
    
    # Check common terminal emulators
    terminals = [
        ["gnome-terminal", "--", "bash", "-c", "./setup.sh; echo 'Done. Press Enter to close.'; read"],
        ["konsole", "-e", "bash", "-c", "./setup.sh; echo 'Done. Press Enter to close.'; read"],
        ["xfce4-terminal", "-e", "bash -c './setup.sh; echo \"Done. Press Enter to close.\"; read'"],
        ["xterm", "-e", "bash", "-c", "./setup.sh; echo 'Done. Press Enter to close.'; read"]
    ]
    
    launched = False
    for cmd in terminals:
        binary = cmd[0]
        if shutil.which(binary):
            print(f"[updater] Launching terminal: {binary} with {setup_sh}")
            subprocess.Popen(cmd, cwd=cwd)
            launched = True
            break
            
    if not launched:
        print("[updater] No terminal emulator found. Running setup.sh in background...")
        subprocess.Popen(["bash", "./setup.sh"], cwd=cwd)
