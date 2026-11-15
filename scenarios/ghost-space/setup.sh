useradd -r -s /usr/sbin/nologin shopfront
mkdir -p /opt/shopfront /var/log/shopfront
chown shopfront: /var/log/shopfront
cat > /opt/shopfront/app.py <<'PY'
import http.server, time
log = open("/var/log/shopfront/access.log", "a", buffering=1)

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"shopfront ok\n"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        try:
            log.write("%s %s %s\n" % (time.strftime("%FT%T"), self.address_string(), fmt % args))
        except OSError:
            pass

http.server.ThreadingHTTPServer(("0.0.0.0", 8080), H).serve_forever()
PY
cat > /etc/systemd/system/shopfront.service <<'UNIT'
[Unit]
Description=Shopfront web app
After=network.target

[Service]
User=shopfront
ExecStart=/usr/bin/python3 /opt/shopfront/app.py
Restart=always

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now shopfront >/dev/null 2>&1
for i in $(seq 20); do curl -sf localhost:8080 >/dev/null && break; sleep 0.5; done
for i in $(seq 50); do curl -s localhost:8080/products >/dev/null; done
# The app's log "grows" to fill the disk (same inode the app holds open)...
avail_kb=$(df --output=avail -k / | tail -1)
fallocate -l $(( (avail_kb - 2048) * 1024 )) /var/log/shopfront/access.log
# ...and someone "cleaned it up" by deleting it.
printf '%s logrotate: removed oversized access.log\n' "$(date +%FT%T)" > /var/log/shopfront/cleanup.log
rm -f /var/log/shopfront/access.log
expect PID "$(systemctl show -p MainPID --value shopfront)"
