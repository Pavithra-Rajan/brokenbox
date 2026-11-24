token=$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')
mkdir -p /opt/deploy/bin /etc/deploy
echo "release-$token" > /etc/deploy/current
chmod 600 /etc/deploy/current
cat > /opt/deploy/bin/deployctl <<'SH'
#!/bin/bash
case "$1" in
  --version) echo "deployctl 2.4.1" ;;
  status)    cat /etc/deploy/current 2>/dev/null || { echo "deployctl: cannot read /etc/deploy/current (are you root?)" >&2; exit 1; } ;;
  *)         echo "usage: deployctl --version | status" >&2; exit 2 ;;
esac
SH
chmod 755 /opt/deploy/bin/deployctl
echo 'export PATH="/opt/deploy/bin:$PATH"' > /etc/profile.d/deploy.sh
expect TOKEN "$token"
