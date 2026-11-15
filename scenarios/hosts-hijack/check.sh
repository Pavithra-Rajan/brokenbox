grep -q '^api_url = http://api.payments.internal:8080$' /etc/checkout/checkout.conf || fail "the checkout config was changed"
out=$(checkout-health 2>&1) || fail "checkout-health still fails: $out"
echo "$out" | grep -q "$TOKEN" || fail "checkout-health passed, but not against the real payments API"
tmpl=/etc/cloud/templates/hosts.debian.tmpl
first=$(awk '!/^ *#/ && / api\.payments\.internal( |$)/ {print $1; exit}' "$tmpl")
[ "$first" = 127.0.0.20 ] || fail "it works now, but /etc/hosts is regenerated at boot from $tmpl, where api.payments.internal still goes to ${first:-nowhere}"
pass "checkout reaches the real payments API, now and after a reboot"
