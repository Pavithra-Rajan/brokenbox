truncate -s 64M /var/lib/tools.img
mkfs.ext4 -q -L tools /var/lib/tools.img
mkdir -p /opt/tools
echo "/var/lib/tools.img /opt/tools ext4 loop,noexec,nodev,nosuid 0 2" >> /etc/fstab
systemctl daemon-reload
mount /opt/tools
token=$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')
cat > /opt/tools/backup.sh <<SH
#!/bin/bash
# nightly config backup
set -e
out=/var/backups/etc-\$(date +%F).tar.gz
tar -czf "\$out" -C / etc/hostname etc/fstab 2>/dev/null
echo "backup written to \$out ($token)"
SH
chown root:root /opt/tools/backup.sh
chmod 755 /opt/tools/backup.sh
expect TOKEN "$token"
