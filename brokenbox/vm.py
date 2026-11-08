"""Thin wrappers around virsh / virt-install / ssh."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from . import config as C


class Error(Exception):
    pass


def log(msg: str) -> None:
    print(f"\033[36m==>\033[0m {msg}", file=sys.stderr, flush=True)


def run(cmd: list[str], check=True, capture=True, input: str | None = None, timeout=None):
    env = dict(os.environ, LIBVIRT_DEFAULT_URI=C.LIBVIRT_URI)
    p = subprocess.run(cmd, text=True, capture_output=capture, input=input, env=env, timeout=timeout)
    if check and p.returncode != 0:
        err = (p.stderr or p.stdout or "").strip() if capture else ""
        raise Error(f"command failed ({p.returncode}): {shlex.join(cmd)}\n{err}")
    return p


def virsh(*args, check=True):
    return run(["virsh", "-c", C.LIBVIRT_URI, *args], check=check)


#  volumes

def vol_exists(name: str) -> bool:
    return virsh("vol-info", "--pool", C.POOL, name, check=False).returncode == 0


def vol_delete(name: str) -> None:
    if vol_exists(name):
        virsh("vol-delete", "--pool", C.POOL, name)


def vol_upload(name: str, local: Path, fmt: str) -> None:
    vol_delete(name)
    size = local.stat().st_size
    virsh("vol-create-as", C.POOL, name, str(size), "--format", fmt)
    virsh("vol-upload", "--pool", C.POOL, name, str(local))
    virsh("pool-refresh", C.POOL)


def vol_overlay(name: str, backing: str, size: str = C.DISK_SIZE) -> None:
    vol_delete(name)
    virsh("vol-create-as", C.POOL, name, size, "--format", "qcow2",
          "--backing-vol", backing, "--backing-vol-format", "qcow2")


#  domains

def dom_exists(name: str) -> bool:
    return virsh("dominfo", name, check=False).returncode == 0


def dom_state(name: str) -> str:
    p = virsh("domstate", name, check=False)
    return p.stdout.strip() if p.returncode == 0 else "absent"


def dom_destroy(name: str) -> None:
    if not dom_exists(name):
        return
    if dom_state(name) != "shut off":
        virsh("destroy", name, check=False)
    snaps = virsh("snapshot-list", name, "--name", check=False).stdout.split()
    for s in snaps:
        virsh("snapshot-delete", name, s, "--metadata", check=False)
    virsh("undefine", name, "--nvram", check=False)
    if dom_exists(name):
        virsh("undefine", name)


def dom_create(name: str, disk_vol: str, seed_vol: str, memory: int, vcpus: int) -> None:
    run([
        "virt-install", "--connect", C.LIBVIRT_URI,
        "--name", name, "--memory", str(memory), "--vcpus", str(vcpus),
        "--import", "--osinfo", C.OS_VARIANT,
        "--disk", f"vol={C.POOL}/{disk_vol},bus=virtio",
        # Debian's cloud kernel has no SATA/IDE driver, so the NoCloud seed goes on a
        # read-only virtio disk (cloud-init finds it by its 'cidata' volume label).
        "--disk", f"vol={C.POOL}/{seed_vol},device=disk,bus=virtio,readonly=on",
        "--network", f"network={C.NETWORK},model=virtio",
        "--graphics", "none", "--console", "pty,target_type=serial",
        "--noautoconsole", "--quiet",
    ])


def dom_ip(name: str, timeout: int = 180) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for source in ("lease", "arp"):
            p = virsh("domifaddr", name, "--source", source, check=False)
            m = re.search(r"ipv4\s+(\d+\.\d+\.\d+\.\d+)", p.stdout)
            if m:
                return m.group(1)
        time.sleep(2)
    raise Error(f"{name}: no IP address after {timeout}s")


def dom_detach_seed(name: str, seed_vol: str) -> None:
    """Unplug the cloud-init seed disk (live + persistent config)."""
    out = virsh("domblklist", name, "--details").stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[3].endswith("/" + seed_vol):
            virsh("detach-disk", name, parts[2], "--live", "--config", check=False)
            virsh("detach-disk", name, parts[2], "--config", check=False)


def wait_shutoff(name: str, timeout: int) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if dom_state(name) == "shut off":
            return
        time.sleep(5)
    raise Error(f"{name}: did not power off within {timeout}s")


#  cloud-init seed

def make_seed(vol_name: str, user_data: str, instance_id: str, hostname: str) -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "user-data").write_text(user_data)
        (d / "meta-data").write_text(f"instance-id: {instance_id}\nlocal-hostname: {hostname}\n")
        iso = d / "seed.iso"
        run(["xorriso", "-as", "mkisofs", "-quiet", "-output", str(iso), "-volid", "cidata",
             "-joliet", "-rock", str(d / "user-data"), str(d / "meta-data")])
        vol_upload(vol_name, iso, "raw")


#  keys + ssh

def ensure_keys() -> None:
    C.KEY_DIR.mkdir(parents=True, exist_ok=True)
    for k in (C.PLAYER_KEY, C.CONTROL_KEY):
        if not k.exists():
            run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", f"brokenbox-{k.name}", "-f", str(k)])


def pubkey(k: Path) -> str:
    return Path(str(k) + ".pub").read_text().strip()


SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=5", "-o", "IdentitiesOnly=yes"]


def ssh_cmd(ip: str, user: str, key: Path) -> list[str]:
    return ["ssh", *SSH_OPTS, "-i", str(key), f"{user}@{ip}"]


def root_exec(ip: str, script: str, timeout: int = 900, stream: bool = False):
    """Pipe a bash script to root over ssh; the script never touches the guest disk."""
    cmd = ssh_cmd(ip, "root", C.CONTROL_KEY) + ["bash", "-s"]
    if stream:
        return run(cmd, check=False, capture=False, input=script, timeout=timeout)
    return run(cmd, check=False, input=script, timeout=timeout)


def wait_ssh(ip: str, timeout: int = 300) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        p = run(ssh_cmd(ip, "root", C.CONTROL_KEY) + ["true"], check=False, timeout=20)
        if p.returncode == 0:
            return
        time.sleep(3)
    raise Error(f"ssh to {ip} not ready after {timeout}s")


#  download

def download_cloud_image() -> Path:
    C.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = C.CACHE_DIR / C.DEBIAN_IMAGE
    sums = urllib.request.urlopen(C.DEBIAN_URL + "SHA512SUMS", timeout=30).read().decode()
    want = next((l.split()[0] for l in sums.splitlines() if l.endswith(" " + C.DEBIAN_IMAGE)), None)
    if not want:
        raise Error("could not find checksum for image")

    def sha(p):
        h = hashlib.sha512()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    if dest.exists() and sha(dest) == want:
        log(f"cloud image cached: {dest}")
        return dest
    log(f"downloading {C.DEBIAN_URL}{C.DEBIAN_IMAGE}")
    tmp = dest.with_suffix(".part")
    run(["curl", "-fL", "--progress-bar", "-o", str(tmp), C.DEBIAN_URL + C.DEBIAN_IMAGE], capture=False)
    if sha(tmp) != want:
        tmp.unlink()
        raise Error("checksum mismatch on downloaded image")
    tmp.rename(dest)
    return dest


#  state (host side only)

def state_path(sid: str) -> Path:
    return C.STATE_DIR / f"{sid}.json"


def load_state(sid: str) -> dict | None:
    p = state_path(sid)
    return json.loads(p.read_text()) if p.exists() else None


def save_state(sid: str, st: dict) -> None:
    C.STATE_DIR.mkdir(parents=True, exist_ok=True)
    p = state_path(sid)
    p.write_text(json.dumps(st, indent=2))
    p.chmod(0o600)


def clear_state(sid: str) -> None:
    state_path(sid).unlink(missing_ok=True)
