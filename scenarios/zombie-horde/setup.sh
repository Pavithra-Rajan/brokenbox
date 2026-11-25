useradd -r -s /usr/sbin/nologin jobq
mkdir -p /opt/jobq /var/lib/jobq
chown jobq: /var/lib/jobq
cat > /opt/jobq/jobq.py <<'PY'
import os, sys, time

def run_job(n):
    with open("/var/lib/jobq/jobs.log", "a") as f:
        f.write("job %d done at %d\n" % (n, time.time()))

n = 0
batch = 300  # catch up on the backlog first
while True:
    for _ in range(batch):
        n += 1
        if os.fork() == 0:
            run_job(n)
            os._exit(0)
    batch = 2
    time.sleep(3)
PY
cat > /etc/systemd/system/jobq.service <<'UNIT'
[Unit]
Description=Job queue runner

[Service]
User=jobq
ExecStart=/usr/bin/python3 /opt/jobq/jobq.py
Restart=always

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now jobq >/dev/null 2>&1
sleep 5
