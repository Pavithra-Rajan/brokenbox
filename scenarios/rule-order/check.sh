ip=$(ip -4 -o route get 1.1.1.1 | sed -n 's/.* src \([0-9.]*\).*/\1/p')
out=$(curl -s --max-time 4 "http://$ip:9090/") || fail "port 9090 is still unreachable on $ip"
echo "$out" | grep -q "$TOKEN" || fail "something answers on 9090, but it isn't the metrics service"
curl -s --max-time 4 -o /dev/null "http://$ip:9091/" && fail "port 9091 (admin UI) is reachable now. Only 9090 should be opened."
f=/etc/iptables/rules.v4
iptables-restore --test "$f" 2>/dev/null || fail "$f is missing or isn't valid iptables-restore input"
acc=$(grep -n -- '-A INPUT.*--dport 9090.*-j ACCEPT' "$f" | head -1 | cut -d: -f1)
rej=$(grep -n -- '-A INPUT.*--dport 9000:9999.*-j REJECT' "$f" | head -1 | cut -d: -f1)
[ -n "$acc" ] || fail "the 9090 rule isn't saved in $f, so it's lost at the next boot"
[ -z "$rej" ] || [ "$acc" -lt "$rej" ] || fail "in $f the 9090 ACCEPT still comes after the REJECT, so it's broken again after a boot"
pass "9090 is open, 9091 is still blocked, and the rules are saved"
