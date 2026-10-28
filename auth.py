"""
Authentication and sudo management module for EngineeringHub.
Handles non-interactive authentication for Homebrew casks and administrative actions
without opening Terminal windows or requiring interactive password input.
"""

import os
import sys
import shutil
import tempfile
import subprocess
from typing import Optional, Dict

REPO_DIR = os.path.dirname(os.path.abspath(__file__))

PASSWORD_CANDIDATES = [
    os.path.join(REPO_DIR, "password.txt"),
    os.path.expanduser("~/EngineeringHub/password.txt"),
    os.path.join(REPO_DIR, ".password"),
    os.path.expanduser("~/EngineeringHub/.password"),
    os.path.expanduser("~/.config/EngineeringHub/password.txt"),
    os.path.expanduser("~/.engineeringhub_password"),
]


def get_sudo_password() -> Optional[str]:
    """
    Retrieves the sudo password from environment variables or local password files.
    Skips comment lines (starting with #) and blank lines.
    """
    # 1. Environment variable override
    env_pass = os.environ.get("EH_SUDO_PASSWORD") or os.environ.get("SUDO_PASSWORD")
    if env_pass:
        return env_pass.strip()

    # 2. File candidates
    for path in PASSWORD_CANDIDATES:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            return line
            except Exception:
                continue
    return None


def has_sudo_password() -> bool:
    """Returns True if a valid password is found in configuration."""
    pw = get_sudo_password()
    return bool(pw and len(pw) > 0)


def setup_askpass() -> Optional[str]:
    """
    Creates an askpass executable script in /tmp and returns its path.
    Returns None if no password is configured.
    """
    password = get_sudo_password()
    if not password:
        return None

    uid = os.getuid() if hasattr(os, "getuid") else 0
    temp_dir = tempfile.gettempdir()
    pass_file = os.path.join(temp_dir, f".eh_pass_{uid}")
    askpass_script = os.path.join(temp_dir, f".eh_askpass_{uid}.sh")

    try:
        # Write password to a secure user-only file (0600)
        with open(pass_file, "w", encoding="utf-8") as f:
            f.write(password)
        os.chmod(pass_file, 0o600)

        # Write askpass helper script (0700)
        with open(askpass_script, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\n")
            f.write(f'exec /bin/cat "{pass_file}"\n')
        os.chmod(askpass_script, 0o700)

        return askpass_script
    except Exception:
        return None


def get_auth_env() -> Dict[str, str]:
    """
    Returns an environment dictionary populated with SUDO_ASKPASS and
    Homebrew non-interactive flags.
    """
    env = os.environ.copy()
    askpass_path = setup_askpass()
    if askpass_path:
        env["SUDO_ASKPASS"] = askpass_path

    env["NONINTERACTIVE"] = "1"
    env["HOMEBREW_NO_AUTO_UPDATE"] = "1"
    env["HOMEBREW_NO_ENV_HINTS"] = "1"
    return env


def prime_sudo() -> bool:
    """
    Pre-authenticates sudo credentials cache using sudo -A -v.
    Returns True if authentication succeeded or credentials are valid.
    """
    if not has_sudo_password():
        return False

    askpass = setup_askpass()
    if not askpass:
        return False

    env = get_auth_env()
    try:
        res = subprocess.run(
            ["/usr/bin/sudo", "-A", "-v"],
            env=env,
            capture_output=True,
            timeout=5
        )
        return res.returncode == 0
    except Exception:
        return False


def run_sudo(cmd_args: list, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    """
    Runs a command under sudo non-interactively using SUDO_ASKPASS.
    """
    env = get_auth_env()
    sudo_cmd = ["/usr/bin/sudo", "-A"] + cmd_args
    return subprocess.run(sudo_cmd, env=env, capture_output=True, text=True, timeout=timeout)
