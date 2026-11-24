systemctl is-active -q nginx || fail "nginx isn't running"
out=$(curl -sS --max-time 5 --cacert /etc/ssl/shop-root.pem https://shop.internal/ 2>&1) || fail "curl still fails: $out"
echo "$out" | grep -q "$TOKEN" || fail "https://shop.internal doesn't serve the shop page"
pass "https://shop.internal serves a complete certificate chain"
