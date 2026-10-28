"""
Network utilities for EngineeringHub.
Handles internet connectivity detection and remote queries.
"""

import socket
import urllib.request
import urllib.error
import json
import time
from typing import Optional, Dict, Any


def is_connected(timeout: float = 2.0) -> bool:
    """
    Checks if device has active internet connectivity.
    Tries fast socket connections to well-known IP endpoints,
    then falls back to an HTTP HEAD/GET request.
    """
    # 1. Fast socket checks (IP addresses avoid DNS delay)
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

    # 2. HTTP fallback to a fast CDN / reliable endpoint
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


def get_remote_version(url: str, timeout: float = 3.0) -> Optional[str]:
    """Fetches the latest launcher version string from GitHub."""
    try:
        cache_buster_url = f"{url}?t={int(time.time())}"
        req = urllib.request.Request(
            cache_buster_url,
            headers={
                "Cache-Control": "no-cache",
                "User-Agent": "EngineeringHub/1.32"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8").strip()
    except Exception:
        return None


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
