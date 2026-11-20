token=$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')
mkdir -p /opt/svc /etc/iptables
cat > /opt/svc/serve.py <<'PY'
import http.server, sys
port, body = int(sys.argv[1]), (sys.argv[2] + "\n").encode()
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
PY
for s in "metrics 9090 metrics_up{build=\"$token\"} 1" "admin-ui 9091 admin ui"; do
  name=${s%% *}; rest=${s#* }; port=${rest%% *}; body=${rest#* }
  cat > /etc/systemd/system/$name.service <<UNIT
[Service]
DynamicUser=yes
ExecStart=/usr/bin/python3 /opt/svc/serve.py $port '$body'
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
done
cat > /etc/systemd/system/iptables-restore.service <<'UNIT'
[Unit]
Description=Load firewall rules from /etc/iptables/rules.v4
Before=network-pre.target
Wants=network-pre.target
[Service]
Type=oneshot
ExecStart=/usr/sbin/iptables-restore /etc/iptables/rules.v4
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now metrics admin-ui >/dev/null 2>&1
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --dport 9000:9999 -j REJECT --reject-with tcp-reset
iptables-save > /etc/iptables/rules.v4
systemctl enable iptables-restore >/dev/null 2>&1
iptables -A INPUT -p tcp --dport 9090 -j ACCEPT   # the colleague's attempt
expect TOKEN "$token"
