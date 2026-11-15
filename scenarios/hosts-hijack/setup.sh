token=$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')
mkdir -p /opt/payments /etc/checkout
cat > /opt/payments/api.py <<'PY'
import http.server, json, sys
ip, mode, token = sys.argv[1], sys.argv[2], sys.argv[3]
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if mode == "legacy":
            code, body = 404, b"<html><body><h1>404</h1>payments gateway v1 was retired</body></html>\n"
        elif self.path == "/health":
            code, body = 200, json.dumps({"status": "ok", "service": "payments", "build": token}).encode() + b"\n"
        else:
            code, body = 404, b'{"error":"not found"}\n'
        self.send_response(code); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer((ip, 8080), H).serve_forever()
PY
for svc in "payments-v1 127.0.0.9 legacy" "payments-v2 127.0.0.20 current"; do
  set -- $svc
  cat > /etc/systemd/system/$1.service <<UNIT
[Unit]
Description=Payments API ($3)
[Service]
DynamicUser=yes
ExecStart=/usr/bin/python3 /opt/payments/api.py $2 $3 $token
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
done
systemctl daemon-reload
systemctl enable --now payments-v1 payments-v2 >/dev/null 2>&1
cat > /etc/checkout/checkout.conf <<'CONF'
[payments]
api_url = http://api.payments.internal:8080
CONF
cat > /usr/local/bin/checkout-health <<'SH'
#!/bin/bash
url=$(awk -F' = ' '/^api_url/{print $2}' /etc/checkout/checkout.conf)
code=$(curl -s -o /tmp/.checkout-health -w '%{http_code}' --max-time 5 "$url/health")
if [ "$code" = 200 ]; then echo "OK: payments API healthy ($(cat /tmp/.checkout-health))"; exit 0; fi
echo "FAIL: payments API $url/health answered HTTP $code" >&2; exit 1
SH
chmod 755 /usr/local/bin/checkout-health
# entries in both /etc/hosts and the cloud-init template it is regenerated from at boot
for f in /etc/hosts /etc/cloud/templates/hosts.debian.tmpl; do
  python3 - "$f" <<'PY'
import sys
p = sys.argv[1]
lines = open(p).read().splitlines()
# the stale entry goes near the top, the netops one at the bottom
i = next(i for i, l in enumerate(lines) if l.startswith("127.0.0.1") or "localhost" in l)
lines.insert(i, "127.0.0.9   api.payments.internal   # payments gateway")
lines += ["", "# netops 2026-10: payments API v2", "127.0.0.20  api.payments.internal payments-v2.internal"]
open(p, "w").write("\n".join(lines) + "\n")
PY
done
expect TOKEN "$token"
