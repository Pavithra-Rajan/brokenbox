systemctl is-active -q jobq || fail "jobq isn't running"
before=$(wc -l < /var/lib/jobq/jobs.log 2>/dev/null || echo 0)
for i in 1 2 3 4; do
  z=$(ps -eo stat= | grep -c '^Z')
  [ "$z" -eq 0 ] || fail "there are still $z zombie processes"
  sleep 5
done
after=$(wc -l < /var/lib/jobq/jobs.log 2>/dev/null || echo 0)
[ "$after" -gt "$before" ] || fail "no zombies, but jobq has stopped finishing jobs (/var/lib/jobq/jobs.log isn't growing)"
systemctl is-active -q jobq || fail "jobq stopped running"
pass "no zombies for 15 s and jobq is still working"
