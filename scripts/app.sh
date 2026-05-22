#!/bin/bash

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Plase run as root (sudo)." >&2
    exit 1
fi

APP_USER="supi"
APP_HOME="/opt/supi"
REPO_DIR="${1:-$(pwd)}"

if ! id -u "$APP_USER" >/dev/null 2>&1; then
    useradd -r -m -d "$APP_HOME" -s /usr/sbin/nologin "$APP_USER"
    echo "Added user -supi-"
fi

if id -u "$APP_USER" >/dev/null 2>&1; then
    usermod -a -G video,render,gpio,spi  "$APP_USER"

fi

install -d -o "$APP_USER" -g "$APP_USER" "$APP_HOME"

test -f "$REPO_DIR/worker/supi-8.py" || {
    echo "ERROR: supi-8.py not found in $REPO_DIR/worker"
    exit 1
}

cp -r "$REPO_DIR/worker" "$APP_HOME/"
cp -r "$REPO_DIR/templates" "$APP_HOME/"
chown -R "$APP_USER:$APP_USER" "$APP_HOME"
chmod +x -R "$APP_HOME/worker/"


cat > /etc/sudoers.d/supi <<EOF
# SuPi-8: passwordless sudo for specific commands
supi ALL=(ALL) NOPASSWD: /usr/bin/date
supi ALL=(ALL) NOPASSWD: /usr/bin/systemctl
supi ALL=(ALL) NOPASSWD: /usr/bin/nmcli
supi ALL=(ALL) NOPASSWD: /usr/local/bin/apply-update.sh
EOF

chmod 440 /etc/sudoers.d/supi
echo "sudoers configured for user supi"