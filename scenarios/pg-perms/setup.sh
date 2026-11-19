token=$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')
systemctl enable --now postgresql >/dev/null 2>&1
for i in $(seq 30); do runuser -u postgres -- psql -qc 'select 1' >/dev/null 2>&1 && break; sleep 1; done
runuser -u postgres -- createdb shop
runuser -u postgres -- psql -q shop -c "create table orders(id serial primary key, ref text); insert into orders(ref) values ('$token');"
systemctl stop postgresql
chmod -R 777 /var/lib/postgresql
systemctl start postgresql >/dev/null 2>&1 || true
sleep 2
expect TOKEN "$token"
