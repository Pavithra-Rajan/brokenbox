useradd -r -s /usr/sbin/nologin shop
truncate -s 512M /var/lib/shop-sessions.img
mkfs.ext4 -q -N 30000 -L sessions /var/lib/shop-sessions.img
mkdir -p /var/lib/shop/sessions
echo "/var/lib/shop-sessions.img /var/lib/shop/sessions ext4 loop,nodev,nosuid 0 2" >> /etc/fstab
systemctl daemon-reload
mount /var/lib/shop/sessions
chown shop: /var/lib/shop/sessions
chmod 750 /var/lib/shop/sessions
# Fill every inode: lots of expired sessions plus a few current ones.
fresh=$(python3 - <<'PY'
import os, random, secrets, time
d = "/var/lib/shop/sessions"
now = time.time()
fresh = []
for i in range(40):
    n = "sess_" + secrets.token_hex(16)
    p = os.path.join(d, n)
    open(p, "w").write("user=%d\n" % random.randint(1000, 9999))
    t = now - random.randint(60, 3 * 3600)
    os.utime(p, (t, t)); os.chown(p, *(lambda s: (s.st_uid, s.st_gid))(os.stat(d)))
    fresh.append(n)
while True:
    p = os.path.join(d, "sess_" + secrets.token_hex(16))
    try:
        open(p, "w").close()
    except OSError:
        break
    t = now - random.randint(2 * 86400, 30 * 86400)
    os.utime(p, (t, t))
print(",".join(fresh[:8]))
PY
)
chown -R shop: /var/lib/shop/sessions
expect FRESH "$fresh"
cat > /usr/local/bin/shop-sessions <<'PY'
#!/usr/bin/python3
import os, secrets, sys, time
while True:
    p = "/var/lib/shop/sessions/sess_" + secrets.token_hex(16)
    try:
        with open(p, "w") as f:
            f.write("user=%d\n" % (int(time.time()) % 9000 + 1000))
    except OSError as e:
        print("cannot save session %s: %s" % (p, e.strerror), file=sys.stderr, flush=True)
    time.sleep(5)
PY
chmod 755 /usr/local/bin/shop-sessions
cat > /etc/systemd/system/shop-sessions.service <<'UNIT'
[Unit]
Description=Shop session writer
RequiresMountsFor=/var/lib/shop/sessions

[Service]
User=shop
ExecStart=/usr/local/bin/shop-sessions

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now shop-sessions >/dev/null 2>&1
