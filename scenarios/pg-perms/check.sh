bad=$(find /var/lib/postgresql \( -perm -g+w -o -perm -o+w \) ! -type l | head -3)
[ -z "$bad" ] || fail "still group/world-writable: $(echo $bad)"
d=/var/lib/postgresql/15/main
[ "$(stat -c %U "$d")" = postgres ] || fail "$d must be owned by postgres"
r=$(runuser -u postgres -- psql -tAc "select ref from orders" shop 2>&1) || fail "can't query the shop database: $r"
[ "$r" = "$TOKEN" ] || fail "the shop data isn't what it was"
pass "PostgreSQL is running with sane permissions and the data is intact"
