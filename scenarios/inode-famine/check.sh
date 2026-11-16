d=/var/lib/shop/sessions
findmnt -n "$d" >/dev/null || fail "$d is not mounted any more"
f="$d/sess_brokenbox_check_$$"
runuser -u shop -- sh -c "echo test > $f" 2>/dev/null || fail "the shop user still can't write a session to $d"
rm -f "$f"
use=$(df --output=ipcent "$d" | tail -1 | tr -dc 0-9)
[ "$use" -lt 80 ] || fail "inode use on $d is still ${use}%"
IFS=, read -ra keep <<< "$FRESH"
for n in "${keep[@]}"; do
  [ -e "$d/$n" ] || fail "a recent session ($n) was deleted. Only sessions older than 1 day should go."
done
if grep -rqs "/var/lib/shop/sessions" /etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/crontab /var/spool/cron/crontabs /etc/tmpfiles.d; then
  :
else
  found=""
  for t in $(systemctl list-unit-files --type=timer --state=enabled --no-legend | awk '{print $1}'); do
    svc=$(systemctl show -p Unit --value "$t")
    systemctl cat "$svc" 2>/dev/null | grep -q /var/lib/shop/sessions && found=$t
  done
  [ -n "$found" ] || fail "no automatic cleanup for $d found (cron job, enabled systemd timer, or tmpfiles.d rule)"
fi
pass "sessions can be written again (${use}% inodes used) and old ones are cleaned up automatically"
