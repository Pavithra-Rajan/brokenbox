systemctl is-active -q nginx || fail "nginx isn't running"
systemctl is-active -q app || fail "the app isn't running"
pid=$(systemctl show -p MainPID --value app)
[ "$(ps -o user= -p "$pid")" = app ] || fail "the app must run as the 'app' user"
hdr=$(mktemp); body=$(curl -s -D "$hdr" --max-time 5 http://localhost/)
code=$(head -1 "$hdr" | awk '{print $2}')
[ "$code" = 200 ] || fail "http://localhost/ returns HTTP ${code:-nothing}"
grep -qi '^x-app: inventory' "$hdr" && echo "$body" | grep -q "build $TOKEN" || fail "nginx answers 200, but not with the app's page"
pass "nginx serves the app again"
