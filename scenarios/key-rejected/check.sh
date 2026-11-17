sshd -T 2>/dev/null | grep -qi '^strictmodes yes' || fail "sshd's StrictModes was turned off. Fix the files instead."
ssh -i /root/deploy_key -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o ConnectTimeout=5 deploy@localhost true 2>/dev/null || fail "deploy still can't log in with the key"
pass "deploy can log in with their key"
