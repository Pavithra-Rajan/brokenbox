pid=$(systemctl show -p MainPID --value shopfront)
[ "$pid" = "$PID" ] || fail "shopfront was restarted (PID $PID is now $pid). The task was to free the space without restarting it."
curl -sf --max-time 5 localhost:8080 | grep -q 'shopfront ok' || fail "shopfront isn't answering on :8080"
avail=$(df --output=avail -m / | tail -1 | tr -dc 0-9)
[ "$avail" -gt 1024 ] || fail "only ${avail} MB free on /"
pass "${avail} MB free on / and shopfront kept running (PID $pid)"
