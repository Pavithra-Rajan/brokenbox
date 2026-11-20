useradd -r -s /usr/sbin/nologin worker
mkdir -p /opt/worker /etc/worker /var/lib/worker
chown worker: /var/lib/worker
queue="jobs-$(head -c 3 /dev/urandom | od -An -tx1 | tr -d ' \n')"
cat > /etc/worker/worker.env <<ENV
# worker settings (also sourced by the deploy scripts)
export QUEUE_URL=redis://127.0.0.1:6379/0?queue=$queue
export WORKERS=4
ENV
cat > /opt/worker/worker.py <<'PY'
import os, sys, time
url = os.environ.get("QUEUE_URL")
if not url:
    print("worker: QUEUE_URL is not set, refusing to start", file=sys.stderr, flush=True)
    sys.exit(1)
print("worker: consuming from %s with %s workers" % (url, os.environ.get("WORKERS", "1")), flush=True)
while True:
    with open("/var/lib/worker/heartbeat", "w") as f:
        f.write(url + "\n")
    time.sleep(2)
PY
cat > /etc/systemd/system/worker.service <<'UNIT'
[Unit]
Description=Background job worker

[Service]
User=worker
EnvironmentFile=-/etc/worker/worker.env
ExecStart=/usr/bin/python3 /opt/worker/worker.py
Restart=always
RestartSec=200ms

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable worker >/dev/null 2>&1
systemctl start worker >/dev/null 2>&1 || true
sleep 4
expect QUEUE "$queue"
