src=$(findmnt -n -o SOURCE /opt/tools) || fail "/opt/tools is not mounted any more"
findmnt -n -o OPTIONS /opt/tools | tr , '\n' | grep -qx noexec && fail "/opt/tools is still mounted noexec"
line=$(awk '$2=="/opt/tools"' /etc/fstab)
[ -n "$line" ] || fail "/opt/tools is no longer in /etc/fstab, so it won't be mounted after a reboot"
echo "$line" | awk '{print $4}' | tr , '\n' | grep -qx noexec && fail "/etc/fstab still mounts /opt/tools with noexec, so it breaks again after a reboot"
out=$(/opt/tools/backup.sh 2>&1) || fail "running /opt/tools/backup.sh failed: $out"
echo "$out" | grep -q "$TOKEN" || fail "/opt/tools/backup.sh isn't the original script any more"
pass "/opt/tools/backup.sh runs directly, now and after a reboot"
