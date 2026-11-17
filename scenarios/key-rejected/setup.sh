useradd -m -s /bin/bash deploy
ssh-keygen -q -t ed25519 -N '' -C deploy -f /root/deploy_key
install -o admin -g admin -m 600 /root/deploy_key /home/admin/deploy_key
install -o admin -g admin -m 644 /root/deploy_key.pub /home/admin/deploy_key.pub
mkdir -p /home/deploy/.ssh
cp /root/deploy_key.pub /home/deploy/.ssh/authorized_keys
# a well-meaning "make sure ssh can read it" from another admin
chmod 775 /home/deploy
chmod 777 /home/deploy/.ssh
chown admin:admin /home/deploy/.ssh/authorized_keys
chmod 664 /home/deploy/.ssh/authorized_keys
