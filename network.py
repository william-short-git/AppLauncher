"""
Network utilities for EngineeringHub.
Handles internet connectivity detection and remote queries against the GitHub repository.
"""

import socket
import urllib.request
import urllib.error
import json
import time
import base64
import os
import subprocess
from typing import Optional, Dict, Any, Tuple

from app_model import compare_versions

GITHUB_REPO = "william-short-git/AppLauncher"
VERSION_URL = "https://raw.githubusercontent.com/william-short-git/AppLauncher/main/version.txt"


def is_connected(timeout: float = 2.0) -> bool:
    """
    Checks if device has active internet connectivity.
    Tries fast socket connections to well-known IP endpoints,
    then falls back to HTTP endpoints.
    """
    check_hosts = [
        ("1.1.1.1", 53),
        ("8.8.8.8", 53),
        ("1.0.0.1", 53),
    ]

    for host, port in check_hosts:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (OSError, TimeoutError):
            continue

    try:
        req = urllib.request.Request(
            "https://1.1.1.1",
            headers={"User-Agent": "EngineeringHub/1.32"}
        )
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:
        pass

    try:
        req = urllib.request.Request(
            "https://raw.githubusercontent.com",
            headers={"User-Agent": "EngineeringHub/1.32"}
        )
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:
        pass

    return False


def get_remote_version(url: str = VERSION_URL, timeout: float = 3.0) -> Optional[str]:
    """Fetches the latest launcher version string from GitHub."""
    # 1. First attempt: Direct GitHub Contents API (bypasses raw CDN cache)
    try:
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/version.txt?ref=main"
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": "EngineeringHub/1.32",
                "Accept": "application/vnd.github.v3+json",
                "Cache-Control": "no-cache",
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "content" in data:
                return base64.b64decode(data["content"]).decode("utf-8").strip()
    except Exception:
        pass

    # 2. Fallback: Raw GitHub URL with cache buster
    try:
        cache_buster_url = f"{url}?t={int(time.time())}"
        req = urllib.request.Request(
            cache_buster_url,
            headers={
                "Cache-Control": "no-cache",
                "User-Agent": "EngineeringHub/1.32",
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8").strip()
    except Exception:
        return None


def get_latest_github_commit(repo: str = GITHUB_REPO, timeout: float = 3.0) -> Optional[str]:
    """Fetches the latest commit SHA on the main branch of the GitHub repo."""
    try:
        url = f"https://api.github.com/repos/{repo}/commits/main"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "EngineeringHub/1.32",
                "Accept": "application/vnd.github.v3+json",
                "Cache-Control": "no-cache",
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("sha")
    except Exception:
        return None


def get_local_git_commit() -> Optional[str]:
    """Returns the current commit SHA of the local git repository if available."""
    repo_dir = os.path.expanduser("~/EngineeringHub")
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=2
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None


def check_launcher_github_update(current_version: str = "1.32") -> Tuple[bool, Optional[str], str]:
    """
    Checks the GitHub repository for updates to EngineeringHub.
    Evaluates both version.txt and commit history against the GitHub repo.
    Returns: (update_available, target_version, reason)
    """
    remote_version = get_remote_version()
    if remote_version and compare_versions(remote_version, current_version) > 0:
        return True, remote_version, f"New version v{remote_version} released on GitHub"

    # Also check git commit discrepancies if on a cloned system
    remote_sha = get_latest_github_commit()
    local_sha = get_local_git_commit()

    if remote_sha and local_sha and remote_sha != local_sha:
        # Check if local repo is behind remote main
        try:
            repo_dir = os.path.expanduser("~/EngineeringHub")
            fetch_res = subprocess.run(
                ["git", "ls-remote", "origin", "main"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=3
            )
            if fetch_res.returncode == 0:
                remote_git_sha = fetch_res.stdout.split()[0] if fetch_res.stdout.split() else ""
                if remote_git_sha and remote_git_sha != local_sha:
                    target_v = remote_version or current_version
                    return True, target_v, f"New commits pushed to GitHub ({remote_git_sha[:7]})"
        except Exception:
            pass

    return False, remote_version or current_version, "Up to date with GitHub repository"


def get_latest_github_release(repo: str, timeout: float = 4.0) -> Optional[Dict[str, Any]]:
    """Fetches the latest release metadata for a GitHub repository."""
    try:
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "EngineeringHub/1.32",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
