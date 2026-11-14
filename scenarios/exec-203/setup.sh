mkdir -p /opt/reporter
printf '%s\r\n' \
  '#!/bin/bash' \
  '# keeps the heartbeat fresh for the monitoring system' \
  'mkdir -p /var/lib/reporter' \
  'while true; do' \
  '  date +%s > /var/lib/reporter/heartbeat' \
  '  sleep 2' \
  'done' > /opt/reporter/reporter.sh
chmod 644 /opt/reporter/reporter.sh
cat > /etc/systemd/system/reporter.service <<'UNIT'
[Unit]
Description=Heartbeat reporter

[Service]
ExecStart=/opt/reporter/reporter.sh

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable reporter >/dev/null 2>&1
systemctl start reporter >/dev/null 2>&1 || true
