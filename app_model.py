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

        elif self.source == "student":
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
