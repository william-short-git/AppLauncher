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
import re
import subprocess
from typing import Optional, Dict, Any, Tuple


def compare_versions(v1: str, v2: str) -> int:
    """
    Compares two version strings (e.g. '1.1.4' vs 'v1.2.0').
    Returns:
       1 if v1 > v2
      -1 if v1 < v2
       0 if v1 == v2
    """
    try:
        from packaging import version
        p1 = version.parse(v1)
        p2 = version.parse(v2)
        if p1 > p2:
            return 1
        elif p1 < p2:
            return -1
        return 0
    except Exception:
        nums1 = [int(n) for n in re.findall(r'\d+', v1)]
        nums2 = [int(n) for n in re.findall(r'\d+', v2)]
        if nums1 > nums2:
            return 1
        elif nums1 < nums2:
            return -1
        return 0


GITHUB_REPO = "william-short-git/AppLauncher"
VERSION_URL = "https://raw.githubusercontent.com/william-short-git/AppLauncher/main/version.txt"

_last_online_check: float = 0.0
_cached_online_result: bool = False


def is_connected(timeout: float = 0.8, cache_ttl: float = 15.0, force: bool = False) -> bool:
    """
    Fast, non-blocking check if device has active internet connectivity.
    Tries quick socket connections on port 443 (HTTPS) to well-known DNS IPs.
    Caches result for cache_ttl seconds to prevent redundant network delays.
    """
    global _last_online_check, _cached_online_result
    now = time.time()
    if not force and (now - _last_online_check < cache_ttl):
        return _cached_online_result

    check_hosts = [
        ("1.1.1.1", 443),
        ("8.8.8.8", 443),
    ]

    for host, port in check_hosts:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                _cached_online_result = True
                _last_online_check = now
                return True
        except (OSError, TimeoutError):
            continue

    try:
        req = urllib.request.Request(
            "https://1.1.1.1",
            headers={"User-Agent": "EngineeringHub"}
        )
        with urllib.request.urlopen(req, timeout=timeout):
            _cached_online_result = True
            _last_online_check = now
            return True
    except Exception:
        pass

    _cached_online_result = False
    _last_online_check = now
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


def check_launcher_github_update(current_version: str = "1.35") -> Tuple[bool, Optional[str], str]:
    """
    Checks the GitHub repository for updates to EngineeringHub.
    Evaluates both version.txt and commit history against the GitHub repo.
    Returns: (update_available, target_version, reason)
    """
    remote_version = get_remote_version()
    if remote_version and compare_versions(remote_version, current_version) > 0:
        return True, remote_version, f"New version v{remote_version} released on GitHub"

    # Check git commit discrepancies if on a cloned system
    remote_sha = get_latest_github_commit()
    local_sha = get_local_git_commit()

    if remote_sha and local_sha and remote_sha != local_sha:
        target_v = remote_version or current_version
        return True, target_v, f"New commits pushed to GitHub ({remote_sha[:7]})"

    return False, remote_version or current_version, "Up to date with GitHub repository"


_github_release_cache: Dict[str, Tuple[float, Any]] = {}


def get_latest_github_release(repo: str, timeout: float = 3.0, cache_ttl: float = 600.0) -> Optional[Dict[str, Any]]:
    """Fetches the latest release metadata for a GitHub repository with caching."""
    now = time.time()
    if repo in _github_release_cache:
        cached_time, cached_data = _github_release_cache[repo]
        if now - cached_time < cache_ttl:
            return cached_data

    try:
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "EngineeringHub",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            _github_release_cache[repo] = (now, data)
            return data
    except Exception:
        pass
    return None
