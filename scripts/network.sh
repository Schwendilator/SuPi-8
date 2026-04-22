#!/bin/bash

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Plase run as root (sudo)." >&2
    exit 1
fi

HOTSPOT_PASS="${HOTSPOT_PASS:-Classic!}"
INTERFACE="wlan0"

MAC=$(cat /sys/class/net/$INTERFACE/address | tr -d ':' | tail -c 5 | tr '[:lower:]' '[:upper:]')
SSID="SuPi-8 $MAC"
echo "Hotspot Name: $SSID"

systemctl stop systemd-resolved 2>/dev/null || true
systemctl disable systemd-resolved 2>/dev/null || true

nmcli connection delete supi-8-hotspot 2>/dev/null || true
nmcli connection add \
    type wifi \
    ifname $INTERFACE \
    con-name supi-8-hotspot \
    autoconnect yes \
    ssid "$SSID"

# wifi-sec stuff apparently necessary for iPhone    
nmcli connection modify supi-8-hotspot \
    802-11-wireless.mode ap \
    802-11-wireless.band bg \
    ipv4.method manual \
    ipv4.addresses 10.42.0.1/24 \
    ipv4.never-default yes \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.proto rsn \
    wifi-sec.pairwise ccmp \
    wifi-sec.group ccmp \
    wifi-sec.psk "$HOTSPOT_PASS" \
    connection.autoconnect no

for conn in $(nmcli -t -f NAME,TYPE connection show | grep wifi | cut -d: -f1); do
    if [ "$conn" != "supi-8-hotspot" ]; then
        nmcli connection modify "$conn" \
            connection.autoconnect yes \
            connection.autoconnect-priority 100 \
            connection.autoconnect-retries 3
        echo "Client-WLAN priorisiert: $conn"
    fi
done

cat > /etc/dnsmasq.conf <<EOF
interface=$INTERFACE
bind-interfaces
dhcp-range=10.42.0.10,10.42.0.200,12h
address=/#/10.42.0.1
EOF

systemctl enable dnsmasq
systemctl stop dnsmasq 2>/dev/null || true


iptables -t nat -F PREROUTING
iptables -t nat -A PREROUTING -i $INTERFACE -p tcp --dport 80 -j REDIRECT --to-port 5091
netfilter-persistent save

cat > /etc/NetworkManager/dispatcher.d/50-supi8-wifi <<'DISPATCHER'
#!/bin/bash
INTERFACE="wlan0"
HOTSPOT="supi-8-hotspot"

[ "$1" != "$INTERFACE" ] && exit 0

logger "SuPi-8 dispatcher: event=$2"

case "$2" in
    up)
        ACTIVE=$(nmcli -t -f NAME,DEVICE con show --active | awk -F: '$2=="wlan0"{print $1}')
        if [[ -n "$ACTIVE" && "$ACTIVE" != "$HOTSPOT" ]]; then
            # Client WiFi came up — stop hotspot
            logger "SuPi-8: Client WiFi up ($ACTIVE), stopping hotspot"
            nmcli con down "$HOTSPOT" 2>/dev/null || true
            systemctl stop dnsmasq
        elif [[ "$ACTIVE" == "$HOTSPOT" ]]; then
            # Hotspot came up — start dnsmasq
            logger "SuPi-8: Hotspot up, starting dnsmasq"
            systemctl start dnsmasq
        fi
        ;;
    down)
        sleep 15
        ACTIVE=$(nmcli -t -f NAME,DEVICE con show --active | awk -F: '$2=="wlan0"{print $1}')
        if [ -z "$ACTIVE" ]; then
            logger "SuPi-8: No WiFi after drop - starting hotspot"
            nmcli con up "$HOTSPOT"
            systemctl start dnsmasq
        else
            logger "SuPi-8: WiFi came back ($ACTIVE) - staying in client mode"
        fi
        ;;
esac
DISPATCHER

chmod +x /etc/NetworkManager/dispatcher.d/50-supi8-wifi

echo "Connection going down for a moment!"
systemctl restart NetworkManager


echo ""
echo "Hotspot SSID:     $SSID"
echo "Hotspot Password: $HOTSPOT_PASS"
echo "Hotspot IP:       10.42.0.1"

sleep 2