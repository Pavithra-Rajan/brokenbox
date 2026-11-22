token=$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')
useradd -r -s /usr/sbin/nologin app
mkdir -p /opt/app /etc/app
cat > /etc/app/app.conf <<'CONF'
[server]
# unix socket the app listens on
socket = /run/app/app.sock
# permissions for the socket file (octal)
mode = 0600
CONF
cat > /opt/app/app.py <<PY
import configparser, http.server, os, socketserver
cfg = configparser.ConfigParser(); cfg.read("/etc/app/app.conf"); c = cfg["server"]
path, mode = c["socket"], int(c.get("mode", "0600"), 8)

class H(http.server.BaseHTTPRequestHandler):
    def address_string(self): return "unix"
    def do_GET(self):
        body = b"<h1>Inventory</h1><p>42 items in stock</p><!-- build $token -->\n"
        self.send_response(200); self.send_header("Content-Type", "text/html")
        self.send_header("X-App", "inventory"); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

class S(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

if os.path.exists(path): os.unlink(path)
srv = S(path, H)
os.chmod(path, mode)
print("listening on", path, oct(mode), flush=True)
srv.serve_forever()
PY
cat > /etc/systemd/system/app.service <<'UNIT'
[Unit]
Description=Inventory app
[Service]
User=app
Group=app
RuntimeDirectory=app
ExecStart=/usr/bin/python3 /opt/app/app.py
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
rm -f /etc/nginx/sites-enabled/default
cat > /etc/nginx/sites-available/app <<'NGX'
server {
    listen 80 default_server;
    server_name _;
    location / {
        proxy_pass http://unix:/run/app.sock;
        proxy_set_header Host $host;
    }
}
NGX
ln -sf /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app
systemctl daemon-reload
systemctl enable --now app nginx >/dev/null 2>&1
curl -s -o /dev/null localhost/ || true
expect TOKEN "$token"
