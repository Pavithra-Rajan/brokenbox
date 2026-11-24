token=$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')
ca=$(mktemp -d); cd $ca
q() { openssl "$@" >/dev/null 2>&1; }
q req -x509 -newkey rsa:2048 -nodes -keyout root.key -out root.crt -days 3650 -subj "/O=Shop/CN=Shop Root CA" \
  -addext basicConstraints=critical,CA:true -addext keyUsage=critical,keyCertSign,cRLSign
q req -newkey rsa:2048 -nodes -keyout int.key -out int.csr -subj "/O=Shop/CN=Shop Issuing CA 1"
printf 'basicConstraints=critical,CA:true,pathlen:0\nkeyUsage=critical,keyCertSign,cRLSign\n' > int.ext
q x509 -req -in int.csr -CA root.crt -CAkey root.key -CAcreateserial -out int.crt -days 1825 -extfile int.ext
q req -newkey rsa:2048 -nodes -keyout leaf.key -out leaf.csr -subj "/O=Shop/CN=shop.internal"
printf 'subjectAltName=DNS:shop.internal\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:false\n' > leaf.ext
q x509 -req -in leaf.csr -CA int.crt -CAkey int.key -CAcreateserial -out leaf.crt -days 365 -extfile leaf.ext
mkdir -p /etc/nginx/tls /var/www/shop
install -m 644 leaf.crt /etc/nginx/tls/shop.internal.crt
install -m 600 leaf.key /etc/nginx/tls/shop.internal.key
install -m 644 int.crt  /etc/nginx/tls/shop-issuing-ca-1.crt
install -m 644 root.crt /etc/ssl/shop-root.pem
cd /; rm -rf $ca
echo "<h1>Shop</h1><!-- $token -->" > /var/www/shop/index.html
grep -q shop.internal /etc/hosts || echo "127.0.0.1 shop.internal" >> /etc/hosts
grep -q shop.internal /etc/cloud/templates/hosts.debian.tmpl || echo "127.0.0.1 shop.internal" >> /etc/cloud/templates/hosts.debian.tmpl
rm -f /etc/nginx/sites-enabled/default
cat > /etc/nginx/sites-enabled/shop <<'NGX'
server {
    listen 443 ssl;
    server_name shop.internal;
    ssl_certificate     /etc/nginx/tls/shop.internal.crt;
    ssl_certificate_key /etc/nginx/tls/shop.internal.key;
    root /var/www/shop;
}
NGX
systemctl enable --now nginx >/dev/null 2>&1
systemctl reload nginx
expect TOKEN "$token"
