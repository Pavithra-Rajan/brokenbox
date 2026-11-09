"""Scenario discovery and the scripts the tool wraps around them."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import config as C


@dataclass
class Scenario:
    id: str
    path: Path
    title: str
    difficulty: str = "easy"
    kind: str = "Fix"
    time_minutes: int = 15
    sudo: bool = True
    memory: int = 1024
    vcpus: int = 1
    description: str = ""
    test: str = ""
    inspired_by: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def setup_script(self) -> str:
        return (self.path / "setup.sh").read_text()

    @property
    def check_script(self) -> str:
        return (self.path / "check.sh").read_text()


def load(path: Path) -> Scenario:
    meta = tomllib.loads((path / "scenario.toml").read_text())
    known = Scenario.__dataclass_fields__.keys()
    return Scenario(id=path.name, path=path, **{k: v for k, v in meta.items() if k in known})


def all_scenarios() -> list[Scenario]:
    order = {"easy": 0, "medium": 1, "hard": 2}
    out = [load(p) for p in sorted(C.SCENARIOS_DIR.iterdir()) if (p / "scenario.toml").exists()]
    return sorted(out, key=lambda s: (order.get(s.difficulty, 9), s.id))


def get(sid: str) -> Scenario:
    p = C.SCENARIOS_DIR / sid
    if not (p / "scenario.toml").exists():
        raise KeyError(sid)
    return load(p)


# Prepended to every setup.sh. setup.sh runs as root over ssh stdin, so it is never
# written to the guest disk. Call `expect KEY value` to record an answer on the HOST;
# check.sh receives it as $KEY.
SETUP_PRELUDE = r"""
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
expect() { echo "##brokenbox:expect $1=$2"; }
as_admin() { sudo -u admin -H bash -c "$*"; }
"""

# Runs after setup.sh: lock down sudo if requested and scrub traces.
POST_SETUP = r"""
set -u
if [ "${BROKENBOX_SUDO}" = "false" ]; then
  rm -f /etc/sudoers.d/90-cloud-init-users
  gpasswd -d admin sudo >/dev/null 2>&1 || true
fi
rm -f /var/lib/cloud/instance/user-data.txt* /var/lib/cloud/instances/*/user-data.txt*
journalctl --rotate >/dev/null 2>&1; journalctl --vacuum-time=1s >/dev/null 2>&1
rm -f /root/.bash_history /home/admin/.bash_history
sync
"""

CHECK_PRELUDE = r"""
set -u
cd /tmp
pass() { echo "PASS: $*"; exit 0; }
fail() { echo "FAIL: $*"; exit 1; }
"""


def user_data(hostname: str, player_pub: str, control_pub: str) -> str:
    return f"""#cloud-config
hostname: {hostname}
manage_etc_hosts: true
ssh_pwauth: false
disable_root: false
users:
  - name: admin
    gecos: admin
    groups: [adm, sudo, systemd-journal]
    shell: /bin/bash
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    lock_passwd: true
    ssh_authorized_keys: ["{player_pub}"]
  - name: root
    ssh_authorized_keys: ["{control_pub}"]
"""


def golden_user_data(control_pub: str) -> str:
    pkgs = "\n".join(f"  - {p}" for p in C.GOLDEN_PACKAGES)
    disable = " ".join(C.GOLDEN_DISABLE)
    return f"""#cloud-config
hostname: brokenbox-golden
disable_root: false
users:
  - name: root
    ssh_authorized_keys: ["{control_pub}"]
package_update: true
packages:
{pkgs}
runcmd:
  - [sh, -c, "systemctl disable --now {disable} || true"]
  - [sh, -c, "apt-get clean"]
  - [sh, -c, "truncate -s0 /etc/machine-id; rm -f /var/lib/dbus/machine-id"]
power_state:
  mode: poweroff
  timeout: 120
  condition: true
"""
