exe=$(systemctl show -p ExecStart --value reporter | sed -n 's/.*argv\[\]=\([^ ;]*\).*/\1/p')
[ "$exe" = "/opt/reporter/reporter.sh" ] || fail "ExecStart was changed (it runs '$exe'). Fix the script, not the unit."
systemctl is-enabled -q reporter || fail "reporter isn't enabled, so it won't start at boot"
systemctl is-active -q reporter || fail "reporter isn't running"
h=/var/lib/reporter/heartbeat
[ -f "$h" ] || fail "$h doesn't exist"
a=$(cat "$h"); sleep 5; b=$(cat "$h")
[ "$a" != "$b" ] || fail "$h isn't being updated"
pass "reporter is running and the heartbeat is fresh"
