for l in /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock; do
  [ -e "$l" ] || fail "$l was deleted"
done
systemctl is-active -q apt-nightly && fail "apt-nightly is still running"
systemctl is-enabled -q apt-nightly 2>/dev/null && fail "apt-nightly is still enabled, so it comes back at the next boot"
pgrep -f apt-nightly >/dev/null && fail "an apt-nightly process is still running"
h=$(fuser /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock 2>/dev/null | tr -s ' ')
[ -z "$h" ] || fail "something still holds the dpkg locks (PIDs:$h)"
a=$(dpkg --audit 2>&1)
[ -z "$a" ] || fail "dpkg --audit still reports problems: $(echo "$a" | head -3)"
dpkg-query -W -f='${Status}' acme-agent 2>/dev/null | grep -q 'install ok installed' || fail "acme-agent isn't fully installed"
apt-get -qq check >/dev/null 2>&1 || fail "apt-get check fails"
pass "dpkg is unlocked and healthy"
