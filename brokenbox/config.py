"""Paths and constants."""
import os
from pathlib import Path

LIBVIRT_URI = os.environ.get("BROKENBOX_LIBVIRT_URI", "qemu:///system")
POOL = os.environ.get("BROKENBOX_POOL", "default")
NETWORK = os.environ.get("BROKENBOX_NETWORK", "default")
PREFIX = "brokenbox"

DEBIAN_URL = "https://cloud.debian.org/images/cloud/bookworm/latest/"
DEBIAN_IMAGE = "debian-12-genericcloud-amd64.qcow2"
OS_VARIANT = "debian12"

CLOUD_VOL = f"{PREFIX}-debian12-cloud.qcow2"   # pristine upstream image
GOLDEN_VOL = f"{PREFIX}-golden.qcow2"          # cloud image + packages
DISK_SIZE = "10G"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = Path(os.environ.get("BROKENBOX_SCENARIOS", PROJECT_ROOT / "scenarios"))

DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "brokenbox"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "brokenbox"
STATE_DIR = DATA_DIR / "state"
KEY_DIR = DATA_DIR / "keys"
PLAYER_KEY = KEY_DIR / "player"     # you log in as admin with this
CONTROL_KEY = KEY_DIR / "control"   # tool logs in as root with this (setup/check)

# Packages baked into the golden image. Services are disabled; scenarios enable what they need.
GOLDEN_PACKAGES = [
    "sudo", "curl", "wget", "git", "jq", "vim", "nano", "less", "tree", "file",
    "lsof", "psmisc", "procps", "strace", "net-tools", "iproute2", "dnsutils",
    "iptables", "netcat-openbsd", "tcpdump", "rsync", "python3", "openssl",
    "nginx", "postgresql", "postgresql-client", "docker.io", "bc", "gawk",
    "man-db", "htop", "sysstat", "ca-certificates", "cron",
]
GOLDEN_DISABLE = ["nginx", "postgresql", "docker", "docker.socket", "containerd"]


def domain_name(scenario_id: str) -> str:
    return f"{PREFIX}-{scenario_id}"
