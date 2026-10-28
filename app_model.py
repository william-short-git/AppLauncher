"""
Data model and behavior encapsulation for managed engineering applications.
Provides unified detection, versioning, launch, and status determination.
"""

import os
import plistlib
import subprocess
from typing import Optional, List, Dict, Any
import network
from network import compare_versions


def get_running_gui_apps() -> set:
    """Returns lowercased process names of all running GUI apps on macOS."""
    for _ in range(2):
        try:
            res = subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to get name of every process whose background only is false'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if res.returncode == 0:
                return {p.strip().lower() for p in res.stdout.split(",") if p.strip()}
            time.sleep(0.2)
        except Exception:
            time.sleep(0.2)
    return set()


class App:
    """Represents a managed application and its operational lifecycle."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.id = data.get("id", data.get("name", "").lower().replace(" ", "_"))
        self.name = data["name"]
        self.icon = data.get("icon", "📦")
        self.icon_path = data.get("icon_path", "")
        self.category = data.get("category", "General")
        self.app_name = data.get("app_name", self.name)
        self.source = data.get("source", "brew")
        self.cask = data.get("cask")
        self.repo = data.get("repo")
        self.desc = data.get("desc", "")
        self.url = data.get("url", "")
        self._cached_release_tag: Optional[str] = None

    @property
    def is_student(self) -> bool:
        return self.source == "student"

    def find_app_path(self) -> Optional[str]:
        """
        Locates the installed .app bundle across standard macOS application paths.
        Checks /Applications, ~/Applications, and subfolders.
        """
        candidates = [
            f"/Applications/{self.app_name}.app",
            os.path.expanduser(f"~/Applications/{self.app_name}.app"),
            f"/Applications/{self.app_name}/{self.app_name}.app",
            os.path.expanduser(f"~/Applications/{self.app_name}/{self.app_name}.app"),
        ]

        # Additional aliases for specific applications
        if self.app_name == "Autodesk Fusion 360":
            candidates.extend([
                "/Applications/Autodesk Fusion.app",
                os.path.expanduser("~/Applications/Autodesk Fusion.app"),
                "/Applications/Autodesk/Autodesk Fusion.app",
            ])
            # Check Autodesk webdeploy streaming installation path
            import glob
            webdeploy_matches = glob.glob(
                os.path.expanduser("~/Library/Application Support/Autodesk/webdeploy/production/*/Autodesk Fusion.app")
            )
            candidates.extend(webdeploy_matches)
        elif self.app_name == "KiCad":
            candidates.extend([
                "/Applications/KiCad/KiCad.app",
                "/Applications/KiCad/kicad.app",
                "/Applications/KiCad.app",
                "/Applications/kicad.app",
                os.path.expanduser("~/Applications/KiCad/KiCad.app"),
                os.path.expanduser("~/Applications/KiCad.app"),
            ])

        for path in candidates:
            if os.path.exists(path) and os.path.isdir(path):
                # Verify it looks like a valid macOS application bundle
                if os.path.exists(os.path.join(path, "Contents")):
                    return path

        return None

    def is_installed(self) -> bool:
        """Returns True if the application bundle is present on the filesystem."""
        return self.find_app_path() is not None

    def get_installed_version(self) -> Optional[str]:
        """Reads the application version from Contents/Info.plist."""
        path = self.find_app_path()
        if not path:
            return None

        plist_path = os.path.join(path, "Contents", "Info.plist")
        if not os.path.isfile(plist_path):
            return None

        try:
            with open(plist_path, "rb") as f:
                data = plistlib.load(f)
                return data.get("CFBundleShortVersionString") or data.get("CFBundleVersion")
        except Exception:
            return None

    def get_bundle_id(self) -> Optional[str]:
        """Returns CFBundleIdentifier from app Info.plist if available."""
        path = self.find_app_path()
        if not path:
            return None
        plist_path = os.path.join(path, "Contents", "Info.plist")
        if os.path.exists(plist_path):
            try:
                with open(plist_path, "rb") as f:
                    data = plistlib.load(f)
                    return data.get("CFBundleIdentifier")
            except Exception:
                pass
        return None

    def launch(self) -> bool:
        """Launches the application via macOS open command."""
        path = self.find_app_path()
        try:
            if path:
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["open", "-a", self.app_name])
            return True
        except Exception:
            return False

    def is_running(self, running_apps_set: Optional[set] = None) -> bool:
        """Checks if the application is currently running."""
        if running_apps_set is None:
            running_apps_set = get_running_gui_apps()

        possible_names = {self.name.lower(), self.app_name.lower()}
        if self.id == "vscode" or "visual studio code" in self.name.lower():
            possible_names.update(["code", "visual studio code", "electron"])
        elif self.id == "kicad":
            possible_names.update(["kicad", "kicad.app"])
        elif self.id == "fusion":
            possible_names.update(["autodesk fusion", "autodesk fusion 360", "fusion360", "fusion"])
        elif self.id == "freecad":
            possible_names.update(["freecad"])
        elif self.id == "ltspice":
            possible_names.update(["ltspice", "crossover", "ltspicexvii"])
        elif self.id == "antigravity":
            possible_names.update(["antigravity"])

        return bool(possible_names.intersection(running_apps_set))

    def close(self) -> bool:
        """Gracefully closes the running application."""
        bundle_id = self.get_bundle_id()
        if bundle_id:
            try:
                subprocess.run(
                    ["osascript", "-e", f'tell application id "{bundle_id}" to quit'],
                    capture_output=True,
                    timeout=3
                )
            except Exception:
                pass

        app_identifiers = [self.name, self.app_name]
        if self.id == "vscode":
            app_identifiers.extend(["Visual Studio Code", "Code"])
        elif self.id == "fusion":
            app_identifiers.extend(["Autodesk Fusion", "Autodesk Fusion 360", "Fusion360"])
        elif self.id == "kicad":
            app_identifiers.extend(["KiCad", "kicad"])
        elif self.id == "ltspice":
            app_identifiers.extend(["LTspice", "LTspiceXVII"])
        elif self.id == "freecad":
            app_identifiers.extend(["FreeCAD", "freecad"])
        elif self.id == "antigravity":
            app_identifiers.append("Antigravity")

        for ident in app_identifiers:
            try:
                subprocess.run(
                    ["osascript", "-e", f'tell application "{ident}" to quit'],
                    capture_output=True,
                    timeout=2
                )
            except Exception:
                pass

        return True

    def check_status(self, installed_casks: set, outdated_casks: dict, is_online: bool = True) -> str:
        """
        Determines application status: 'installed', 'outdated', or 'missing'.
        Always verifies if the application is physically installed first.
        """
        # Step 1: Physical file presence check
        installed = self.is_installed()
        if not installed:
            return "missing"

        # Step 2: If installed, check if outdated
        if self.source == "brew":
            if is_online and self.cask:
                if self.cask in outdated_casks:
                    return "outdated"
            return "installed"

        elif self.source == "github":
            if is_online and self.repo:
                local_ver = self.get_installed_version()
                if local_ver:
                    remote_ver = self.fetch_remote_version()
                    if remote_ver and compare_versions(remote_ver, local_ver) > 0:
                        return "outdated"
            return "installed"

        elif self.source in ("student", "web"):
            return "installed"

        return "installed"

    def fetch_remote_version(self) -> Optional[str]:
        """Fetches the latest release tag for GitHub-sourced applications."""
        if not self.repo:
            return None
        if self._cached_release_tag:
            return self._cached_release_tag

        data = network.get_latest_github_release(self.repo)
        if data and "tag_name" in data:
            tag = data["tag_name"]
            # Clean tag (e.g. 'v1.1.4' -> '1.1.4')
            clean_tag = tag.lstrip("v").strip()
            self._cached_release_tag = clean_tag
            return clean_tag
        return None
