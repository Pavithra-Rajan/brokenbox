systemctl is-active -q worker || fail "worker isn't running"
n1=$(systemctl show -p NRestarts --value worker)
pid1=$(systemctl show -p MainPID --value worker)
sleep 15
systemctl is-active -q worker || fail "worker stopped again"
n2=$(systemctl show -p NRestarts --value worker)
pid2=$(systemctl show -p MainPID --value worker)
[ "$n1" = "$n2" ] && [ "$pid1" = "$pid2" ] || fail "worker is still restarting"
tr '\0' '\n' < /proc/$pid2/environ | grep -q "^QUEUE_URL=.*queue=$QUEUE\$" || fail "worker is running, but not with the QUEUE_URL from /etc/worker/worker.env"
pass "worker is up and stable, consuming from queue $QUEUE"
