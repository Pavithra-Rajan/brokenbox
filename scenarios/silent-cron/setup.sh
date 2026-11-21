if ! command -v cron >/dev/null; then
  apt-get update -qq >/dev/null && apt-get install -y -qq cron >/dev/null
fi
systemctl enable --now cron >/dev/null 2>&1
token=$(head -c 4 /dev/urandom | od -An -tx1 | tr -d ' \n')
mkdir -p /opt/reportkit/bin /var/reports
chown admin: /var/reports
cat > /opt/reportkit/bin/report-gen <<SH
#!/bin/bash
[ "\$1" = --date ] && [ -n "\$2" ] || { echo "usage: report-gen --date YYYY-MM-DD" >&2; exit 2; }
echo "Daily report for \$2"
echo "orders: \$(( RANDOM % 500 ))   build: $token"
SH
chmod 755 /opt/reportkit/bin/report-gen
echo 'export PATH="/opt/reportkit/bin:$PATH"' >> /home/admin/.profile
# written straight into the spool, the way a config tool did it (note: no trailing newline)
printf '# m h dom mon dow command\n* * * * * report-gen --date $(date +%%Y-%%m-%%d) > /var/reports/latest.txt' > /var/spool/cron/crontabs/admin
chown admin:crontab /var/spool/cron/crontabs/admin
chmod 600 /var/spool/cron/crontabs/admin
systemctl restart cron
expect TOKEN "$token"
