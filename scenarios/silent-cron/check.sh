f=/var/reports/latest.txt
crontab -u admin -l >/dev/null 2>&1 || fail "admin has no crontab any more"
systemctl is-active -q cron || fail "the cron daemon isn't running"
start=$(date +%s)
for i in $(seq 40); do
  if [ -f "$f" ] && [ "$(stat -c %Y "$f")" -ge "$start" ]; then
    sleep 1
    grep -q "Daily report for $(date +%F)" "$f" || fail "cron updated $f, but it doesn't contain today's report: $(head -c 200 "$f")"
    grep -q "build: $TOKEN" "$f" || fail "$f wasn't written by report-gen"
    [ "$(stat -c %U "$f")" = admin ] || fail "$f should be written by admin's cron job"
    pass "cron wrote today's report to $f"
  fi
  sleep 2
done
fail "waited 80 s and cron didn't update $f"
