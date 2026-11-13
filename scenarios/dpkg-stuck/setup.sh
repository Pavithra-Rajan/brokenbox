# a small local package, unpacked but never configured (an interrupted run)
b=$(mktemp -d)
mkdir -p $b/pkg/DEBIAN $b/pkg/usr/local/share/acme-agent
echo "agent=1" > $b/pkg/usr/local/share/acme-agent/agent.conf
cat > $b/pkg/DEBIAN/control <<'CTL'
Package: acme-agent
Version: 1.4.2
Architecture: all
Maintainer: ops <ops@example.invalid>
Description: ACME monitoring agent
CTL
printf '#!/bin/sh\nset -e\nexit 0\n' > $b/pkg/DEBIAN/postinst
chmod 755 $b/pkg/DEBIAN/postinst
dpkg-deb -b $b/pkg $b/acme-agent.deb >/dev/null
dpkg --unpack $b/acme-agent.deb >/dev/null
rm -rf $b
# the job that hangs while holding the dpkg locks
cat > /usr/local/sbin/apt-nightly <<'PY'
#!/usr/bin/python3
# nightly unattended package update (v0.3, "temporary")
import fcntl, time
held = []
for p in ("/var/lib/dpkg/lock-frontend", "/var/lib/dpkg/lock"):
    f = open(p, "a")
    fcntl.lockf(f, fcntl.LOCK_EX)
    held.append(f)
print("apt-nightly: updating package lists...", flush=True)
while True:
    time.sleep(3600)   # waiting for a mirror that no longer exists
PY
chmod 755 /usr/local/sbin/apt-nightly
cat > /etc/systemd/system/apt-nightly.service <<'UNIT'
[Unit]
Description=Nightly package update
[Service]
ExecStart=/usr/local/sbin/apt-nightly
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now apt-nightly >/dev/null 2>&1
sleep 1
