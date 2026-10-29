"""
Background worker threads for EngineeringHub.
Encapsulates asynchronous actions (installation, uninstallation, status checks, and self-update)
without blocking the PyQt graphical interface or opening external terminal windows.
"""

import os
import sys
import json
import time
import shutil
import platform
import subprocess
import urllib.request
import webbrowser
from typing import List, Dict, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from app_model import App
from network import compare_versions
import auth
import network

VERSION_URL = "https://raw.githubusercontent.com/william-short-git/AppLauncher/main/version.txt"
APP_VERSION = "1.36"


class AppActionWorker(QThread):
    """
    Worker thread that executes app installation, upgrade, or uninstallation.
    Never opens external terminal windows. Uses SUDO_ASKPASS for silent privilege escalation.
    """
    progress = pyqtSignal(int)
    finished_action = pyqtSignal(bool, str)  # (success, status_message)

    def __init__(self, app: App, action: str):
        super().__init__()
        self.app = app
        self.action = action  # 'install', 'upgrade', or 'uninstall'

    def run(self):
        try:
            if self.action in ("install", "upgrade"):
                self._handle_install_or_upgrade()
            elif self.action == "uninstall":
                self._handle_uninstall()
            else:
                self.finished_action.emit(False, f"Unknown action: {self.action}")
        except Exception as e:
            self.finished_action.emit(False, str(e))

    def _handle_install_or_upgrade(self):
        if self.app.source in ("student", "web"):
            url = self.app.url or "https://antigravity.google/"
            webbrowser.open(url)
            self.finished_action.emit(True, "Opened portal in browser")
            return

        if self.app.source == "brew":
            self._install_brew()
        elif self.app.source == "github":
            self._install_github()
        else:
            self.finished_action.emit(False, f"Unsupported source: {self.app.source}")

    def _install_brew(self):
        brew_bin = shutil.which("brew") or "/opt/homebrew/bin/brew" or "/usr/local/bin/brew"
        if not os.path.exists(brew_bin):
            self.finished_action.emit(False, "Homebrew binary not found")
            return

        env = auth.get_auth_env()
        auth.prime_sudo()

        brew_action = "reinstall" if self.action == "install" else "upgrade"
        cmd = [brew_bin, brew_action, "--cask", self.app.cask]

        self.progress.emit(0)
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if self.app.is_installed() and proc.returncode == 0:
            self.progress.emit(100)
            self.finished_action.emit(True, "Installed successfully")
            return

        # Check for authentication errors
        stderr_text = (proc.stderr or "").lower()
        if "sudo" in stderr_text or "password" in stderr_text or "need sudo" in stderr_text:
            if not auth.has_sudo_password():
                self.finished_action.emit(False, "Password required in password.txt")
            else:
                self.finished_action.emit(False, "Auth failed with password.txt")
        else:
            # Check if app actually landed on disk
            if self.app.is_installed():
                self.finished_action.emit(True, "Installed successfully")
            else:
                err_msg = proc.stderr.strip() if proc.stderr else "Installation failed"
                self.finished_action.emit(False, err_msg[:120])

    def _install_github(self):
        if not self.app.repo:
            self.finished_action.emit(False, "Missing repository name")
            return

        release = network.get_latest_github_release(self.app.repo)
        if not release:
            # Fallback for KiCad if repository was misconfigured
            if "kicad" in self.app.name.lower():
                release = network.get_latest_github_release("KiCad/kicad-source-mirror")

        if not release:
            # If GitHub releases API is unreachable or rate-limited, fallback to Homebrew cask
            if self.app.cask:
                self._install_brew()
                return
            self.finished_action.emit(False, "Could not fetch GitHub release")
            return

        dmg_url = None
        arch = "arm64" if platform.machine() == "arm64" else "x86_64"

        # Match architecture or mac/darwin/universal
        for asset in release.get("assets", []):
            name = asset.get("name", "").lower()
            if name.endswith(".dmg") and (arch in name or "mac" in name or "darwin" in name or "universal" in name):
                dmg_url = asset.get("browser_download_url")
                break

        if not dmg_url:
            for asset in release.get("assets", []):
                if asset.get("name", "").lower().endswith(".dmg"):
                    dmg_url = asset.get("browser_download_url")
                    break

        if not dmg_url:
            if self.app.cask:
                self._install_brew()
                return
            self.finished_action.emit(False, "No macOS DMG found in release assets")
            return

        temp_dmg = f"/tmp/{self.app.app_name}_{int(time.time())}.dmg"

        def reporthook(count, block_size, total_size):
            if total_size > 0:
                p = int(count * block_size * 100 / total_size)
                self.progress.emit(min(p, 95))

        mount_point = f"/tmp/eh_mount_{self.app.app_name}_{int(time.time())}"
        try:
            req = urllib.request.Request(dmg_url, headers={"User-Agent": "EngineeringHub/1.32"})
            with urllib.request.urlopen(req) as resp, open(temp_dmg, "wb") as out_file:
                total_size = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                block_size = 65536
                while True:
                    chunk = resp.read(block_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    reporthook(downloaded // block_size, block_size, total_size)

            self.progress.emit(98)
            os.makedirs(mount_point, exist_ok=True)
            subprocess.run(
                ["hdiutil", "attach", temp_dmg, "-mountpoint", mount_point, "-nobrowse", "-quiet"],
                check=True
            )

            found_app_path = None
            found_suite_dir = None
            for item in os.listdir(mount_point):
                item_full = os.path.join(mount_point, item)
                if item.endswith(".app"):
                    found_app_path = item_full
                    break
                elif os.path.isdir(item_full) and not item.startswith("."):
                    if item.lower() == self.app.app_name.lower():
                        found_suite_dir = item_full

            if not found_app_path:
                for root, dirs, _ in os.walk(mount_point):
                    for d in dirs:
                        if d.endswith(".app"):
                            found_app_path = os.path.join(root, d)
                            break
                    if found_app_path:
                        break

            if not found_app_path and not found_suite_dir:
                self.finished_action.emit(False, "No .app bundle found inside DMG")
                return

            if found_suite_dir:
                dest_dir = f"/Applications/{os.path.basename(found_suite_dir)}"
                if os.path.exists(dest_dir):
                    try:
                        shutil.rmtree(dest_dir)
                    except Exception:
                        auth.run_sudo(["rm", "-rf", dest_dir])
                try:
                    subprocess.run(["cp", "-R", found_suite_dir, "/Applications/"], check=True)
                except Exception:
                    auth.run_sudo(["cp", "-R", found_suite_dir, "/Applications/"])

            if found_app_path:
                dest_app_path = f"/Applications/{os.path.basename(found_app_path)}"
                if not os.path.exists(dest_app_path):
                    try:
                        subprocess.run(["cp", "-R", found_app_path, "/Applications/"], check=True)
                    except Exception:
                        auth.run_sudo(["cp", "-R", found_app_path, "/Applications/"])

            self.progress.emit(100)
            if self.app.is_installed():
                self.finished_action.emit(True, "Installed successfully")
            else:
                self.finished_action.emit(False, "Failed to copy application bundle")

        except Exception as e:
            # Fallback to Homebrew cask on error
            if self.app.cask:
                try:
                    self._install_brew()
                    return
                except Exception:
                    pass
            self.finished_action.emit(False, str(e))

        finally:
            subprocess.run(["hdiutil", "detach", mount_point, "-quiet", "-force"], capture_output=True)
            if os.path.exists(mount_point):
                shutil.rmtree(mount_point, ignore_errors=True)
            if os.path.exists(temp_dmg):
                try:
                    os.remove(temp_dmg)
                except Exception:
                    pass

    def _handle_uninstall(self):
        """Uninstalls the application silently without opening Terminal."""
        if self.app.source == "brew":
            brew_bin = shutil.which("brew") or "/opt/homebrew/bin/brew" or "/usr/local/bin/brew"
            env = auth.get_auth_env()
            auth.prime_sudo()
            cmd = [brew_bin, "uninstall", "--cask", "--force", self.app.cask]
            subprocess.run(cmd, env=env, capture_output=True, text=True)

        # Ensure filesystem bundle is removed
        app_path = self.app.find_app_path()
        if app_path and os.path.exists(app_path):
            try:
                shutil.rmtree(app_path)
            except Exception:
                auth.run_sudo(["rm", "-rf", app_path])

        if not self.app.is_installed():
            self.finished_action.emit(True, "Uninstalled successfully")
        else:
            self.finished_action.emit(False, "Could not completely delete app files")


_brew_cache: Dict[str, Any] = {"timestamp": 0.0, "outdated": {}}
_launcher_cache: Dict[str, Any] = {"timestamp": 0.0, "has_update": False, "target": "", "reason": ""}


class StatusCheckWorker(QThread):
    """
    Lightweight, non-blocking scanner for Homebrew casks and app status.
    Eliminates system-wide scans and sets HOMEBREW_NO_AUTO_UPDATE=1 to prevent CPU spikes.
    """
    finished_check = pyqtSignal(dict)  # {app_name: status_str}

    def __init__(self, apps: List[App], is_periodic: bool = False):
        super().__init__()
        self.apps = apps
        self.is_periodic = is_periodic

    def run(self):
        online = network.is_connected(timeout=0.8)
        outdated_casks = {}

        # Only check casks for applications that are currently installed
        installed_brew_casks = [
            a.cask for a in self.apps
            if a.source == "brew" and a.cask and a.is_installed()
        ]

        if online and installed_brew_casks:
            now = time.time()
            # If periodic check and cache is fresh (< 5 minutes), use cached results
            if self.is_periodic and (now - _brew_cache["timestamp"] < 300.0):
                outdated_casks = _brew_cache["outdated"]
            else:
                brew_bin = shutil.which("brew") or "/opt/homebrew/bin/brew"
                if os.path.exists(brew_bin):
                    env = os.environ.copy()
                    # Prevent Homebrew from running background auto-updates and analytics
                    env["HOMEBREW_NO_AUTO_UPDATE"] = "1"
                    env["HOMEBREW_NO_INSTALL_CLEANUP"] = "1"
                    env["HOMEBREW_NO_ANALYTICS"] = "1"
                    try:
                        outdated_proc = subprocess.run(
                            [brew_bin, "outdated", "--cask", "--json=v2"] + installed_brew_casks,
                            capture_output=True,
                            text=True,
                            timeout=6,
                            env=env
                        )
                        if outdated_proc.returncode == 0:
                            outdated_data = json.loads(outdated_proc.stdout)
                            outdated_casks = {
                                item["name"]: item.get("current_version")
                                for item in outdated_data.get("casks", [])
                            }
                            _brew_cache["timestamp"] = now
                            _brew_cache["outdated"] = outdated_casks
                    except Exception:
                        outdated_casks = _brew_cache.get("outdated", {})

        statuses = {}
        for app in self.apps:
            statuses[app.name] = app.check_status(set(), outdated_casks, is_online=online)

        self.finished_check.emit(statuses)


class LauncherCheckWorker(QThread):
    """Queries GitHub repository for newer versions or commits of EngineeringHub."""
    update_available = pyqtSignal(str, str)  # (version, reason)
    check_completed = pyqtSignal(bool, str)  # (has_update, message)

    def __init__(self, is_periodic: bool = False, parent=None):
        super().__init__(parent)
        self.is_periodic = is_periodic

    def run(self):
        if not network.is_connected(timeout=0.8):
            self.check_completed.emit(False, "Offline: Cannot reach GitHub")
            return

        now = time.time()
        if self.is_periodic and (now - _launcher_cache["timestamp"] < 60.0):
            has_update = _launcher_cache["has_update"]
            target_version = _launcher_cache["target"]
            reason = _launcher_cache["reason"]
        else:
            has_update, target_version, reason = network.check_launcher_github_update(APP_VERSION)
            _launcher_cache["timestamp"] = now
            _launcher_cache["has_update"] = has_update
            _launcher_cache["target"] = target_version
            _launcher_cache["reason"] = reason

        if has_update:
            self.update_available.emit(target_version, reason)
            self.check_completed.emit(True, reason)
        else:
            self.check_completed.emit(False, f"EngineeringHub v{APP_VERSION} is up to date with GitHub")


class LauncherBuilderWorker(QThread):
    """Pulls git updates and recompiles the launcher using PyInstaller."""
    progress = pyqtSignal(int)
    finished_build = pyqtSignal(bool)

    def run(self):
        repo_dir = os.path.expanduser("~/EngineeringHub")
        try:
            self.progress.emit(20)
            subprocess.run(["git", "pull", "origin", "main"], cwd=repo_dir, check=True, capture_output=True)
            self.progress.emit(50)
            pyinstaller_bin = os.path.join(repo_dir, "venv", "bin", "pyinstaller")
            if not os.path.exists(pyinstaller_bin):
                pyinstaller_bin = shutil.which("pyinstaller") or "pyinstaller"

            env = os.environ.copy()
            env["PYINSTALLER_CONFIG_DIR"] = "/tmp/pyinstaller"
            subprocess.run(
                [pyinstaller_bin, "--windowed", "--name", "EngineeringHub", "--add-data", "icons:icons", "--noconfirm", "hub.py"],
                cwd=repo_dir,
                env=env,
                check=True,
                capture_output=True
            )
            self.progress.emit(100)
            self.finished_build.emit(True)
        except Exception:
            self.finished_build.emit(False)


class ProcessPollWorker(QThread):
    """
    Periodically polls running GUI applications in the background so the UI
    remains completely responsive without frame drops.
    """
    running_apps_signal = pyqtSignal(set)

    def __init__(self, interval_seconds: float = 5.0, parent=None):
        super().__init__(parent)
        self.interval = interval_seconds
        self._running = True

    def run(self):
        while self._running:
            from app_model import get_running_gui_apps
            try:
                running_apps = get_running_gui_apps()
                if self._running:
                    self.running_apps_signal.emit(running_apps)
            except Exception:
                pass

            steps = max(1, int(self.interval / 0.1))
            for _ in range(steps):
                if not self._running:
                    return
                time.sleep(0.1)

    def stop(self):
        self._running = False

