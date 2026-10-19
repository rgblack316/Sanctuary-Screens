#!/usr/bin/env bash
# Sanctuary Screens kiosk setup for a display machine (Ubuntu / Debian / Raspberry Pi OS).
# Boots straight into a full-screen Chromium showing /bible or /register. No desktop needed.
#
#   sudo bash setup-kiosk.sh                                   # asks for server IP and display
#   sudo bash setup-kiosk.sh --url http://192.168.1.50:8091/bible
#   sudo bash setup-kiosk.sh --server 192.168.1.50 --display register --rotate left
#   sudo bash setup-kiosk.sh --reboot-at 04:00                 # optional daily reboot
#   sudo bash setup-kiosk.sh --uninstall
#
# Change the URL later: edit /etc/sanctuary-kiosk.conf, then reboot (or: sudo pkill -u kiosk chromium).
set -euo pipefail

KIOSK_USER="kiosk"
CONF=/etc/sanctuary-kiosk.conf
LAUNCHER=/usr/local/bin/sanctuary-kiosk
GETTY_DIR=/etc/systemd/system/getty@tty1.service.d
REBOOT_UNIT=sanctuary-kiosk-reboot

URL=""; SERVER=""; DISPLAY_NAME=""; PORT=8091; ROTATE=normal; REBOOT_AT=""; UNINSTALL=0

die()  { echo "✘ $*" >&2; exit 1; }
info() { echo "==> $*"; }
ok()   { echo "✔ $*"; }

usage() { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [ $# -gt 0 ]; do
  case "$1" in
    --url) URL="$2"; shift 2 ;;
    --server) SERVER="$2"; shift 2 ;;
    --display) DISPLAY_NAME="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --rotate) ROTATE="$2"; shift 2 ;;
    --reboot-at) REBOOT_AT="$2"; shift 2 ;;
    --user) KIOSK_USER="$2"; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help) usage ;;
    *) die "Unknown option $1 (see --help)" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || die "Run with sudo: sudo bash $0 $*"

# ---------- uninstall ----------
if [ $UNINSTALL -eq 1 ]; then
  info "Removing kiosk setup"
  prev_target=""
  [ -f "$CONF" ] && prev_target=$(grep -E '^PREV_DEFAULT_TARGET=' "$CONF" | cut -d= -f2- || true)
  rm -f "$GETTY_DIR/sanctuary-kiosk.conf"
  rmdir "$GETTY_DIR" 2>/dev/null || true
  systemctl disable --now "$REBOOT_UNIT.timer" >/dev/null 2>&1 || true
  rm -f "/etc/systemd/system/$REBOOT_UNIT.timer" "/etc/systemd/system/$REBOOT_UNIT.service"
  if id "$KIOSK_USER" >/dev/null 2>&1; then
    home=$(getent passwd "$KIOSK_USER" | cut -d: -f6)
    rm -f "$home/.bash_profile" "$home/.xinitrc"
  fi
  rm -f "$CONF" "$LAUNCHER"
  [ -n "$prev_target" ] && systemctl set-default "$prev_target" >/dev/null
  systemctl daemon-reload
  ok "Kiosk removed. The '$KIOSK_USER' user was kept (delete with: sudo deluser --remove-home $KIOSK_USER). Reboot to finish."
  exit 0
fi

# ---------- inputs ----------
if [ -z "$URL" ]; then
  [ -n "$SERVER" ] || read -rp "Sanctuary Screens server IP (the NUC): " SERVER
  [ -n "$SERVER" ] || die "Server IP is required."
  if [ -z "$DISPLAY_NAME" ]; then
    read -rp "Which display on this screen? [bible/register] (bible): " DISPLAY_NAME
    DISPLAY_NAME="${DISPLAY_NAME:-bible}"
  fi
  [[ "$DISPLAY_NAME" =~ ^(bible|register)$ ]] || die "--display must be bible or register."
  [[ "$PORT" =~ ^[0-9]+$ ]] || die "--port must be a number."
  URL="http://${SERVER}:${PORT}/${DISPLAY_NAME}"
fi
[[ "$URL" =~ ^https?://[^[:space:]\"\']+$ ]] || die "Invalid URL: $URL"
[[ "$ROTATE" =~ ^(normal|left|right|inverted)$ ]] || die "--rotate must be normal, left, right or inverted."
if [ -n "$REBOOT_AT" ]; then
  [[ "$REBOOT_AT" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]] || die "--reboot-at must be HH:MM (24-hour)."
fi
[[ "$KIOSK_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "Invalid user name."
command -v apt-get >/dev/null 2>&1 || die "This script supports Ubuntu, Debian and Raspberry Pi OS (apt)."

info "Kiosk URL: $URL (rotation: $ROTATE)"

# ---------- packages ----------
info "Installing X, Openbox and Chromium (minimal, no desktop)…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y -qq
apt-get install -y -qq --no-install-recommends xserver-xorg x11-xserver-utils xinit openbox curl ca-certificates >/dev/null

if ! command -v chromium >/dev/null 2>&1 && ! command -v chromium-browser >/dev/null 2>&1; then
  if apt-cache show chromium >/dev/null 2>&1 && ! grep -qi ubuntu /etc/os-release; then
    apt-get install -y -qq --no-install-recommends chromium >/dev/null
  elif command -v snap >/dev/null 2>&1; then
    snap install chromium   # Ubuntu ships Chromium only as a snap
  else
    apt-get install -y -qq --no-install-recommends chromium-browser >/dev/null
  fi
fi
command -v chromium >/dev/null 2>&1 || command -v chromium-browser >/dev/null 2>&1 \
  || [ -x /snap/bin/chromium ] || die "Chromium could not be installed."
ok "Packages installed"

# ---------- user ----------
if ! id "$KIOSK_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash -c "Sanctuary Screens kiosk" "$KIOSK_USER"
  passwd -l "$KIOSK_USER" >/dev/null   # no password login; it only auto-logs in on the local screen
  ok "Created user '$KIOSK_USER' (no sudo, no password)"
fi
for g in video audio input render tty; do
  getent group "$g" >/dev/null && usermod -aG "$g" "$KIOSK_USER"
done
HOME_DIR=$(getent passwd "$KIOSK_USER" | cut -d: -f6)

# ---------- config ----------
prev_target=$(systemctl get-default 2>/dev/null || echo multi-user.target)
[ -f "$CONF" ] && prev_target=$(grep -E '^PREV_DEFAULT_TARGET=' "$CONF" | cut -d= -f2- || echo "$prev_target")
cat > "$CONF" <<EOF
# Sanctuary Screens kiosk settings. After editing, reboot (or: sudo pkill -u $KIOSK_USER chromium).
KIOSK_URL="$URL"
# normal | left | right | inverted  (left/right for portrait screens)
ROTATE="$ROTATE"
# Restore this boot target on --uninstall
PREV_DEFAULT_TARGET=$prev_target
EOF
chmod 644 "$CONF"

# ---------- launcher (waits for the server, restarts Chromium if it exits) ----------
cat > "$LAUNCHER" <<'EOF'
#!/usr/bin/env bash
# Runs inside the kiosk X session. Re-reads /etc/sanctuary-kiosk.conf every time Chromium starts.
CONF=/etc/sanctuary-kiosk.conf

browser() {
  for b in chromium chromium-browser /snap/bin/chromium; do command -v "$b" >/dev/null 2>&1 && { echo "$b"; return; }; done
}

xset s off; xset s noblank; xset -dpms

while true; do
  # shellcheck source=/dev/null
  . "$CONF"
  out=$(xrandr 2>/dev/null | awk '/ connected/{print $1; exit}')
  [ -n "$out" ] && xrandr --output "$out" --rotate "${ROTATE:-normal}" 2>/dev/null

  # Wait until the NUC answers so the screen never shows a "can't reach this page" error.
  until curl -fs -o /dev/null --max-time 4 "$KIOSK_URL"; do sleep 5; done

  "$(browser)" --kiosk "$KIOSK_URL" \
    --incognito --no-first-run --noerrdialogs --disable-infobars \
    --disable-session-crashed-bubble --disable-translate --disable-features=Translate \
    --disable-pinch --overscroll-history-navigation=0 \
    --check-for-update-interval=31536000 --password-store=basic \
    --autoplay-policy=no-user-gesture-required >/dev/null 2>&1
  sleep 3   # Chromium exited or crashed: start it again
done
EOF
chmod 755 "$LAUNCHER"

# ---------- X session for the kiosk user ----------
cat > "$HOME_DIR/.xinitrc" <<EOF
openbox &
exec $LAUNCHER
EOF
cat > "$HOME_DIR/.bash_profile" <<'EOF'
# Start the kiosk on the local screen only (SSH logins get a normal shell).
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
  exec startx -- -nocursor >/dev/null 2>&1
fi
EOF
chown "$KIOSK_USER:$KIOSK_USER" "$HOME_DIR/.xinitrc" "$HOME_DIR/.bash_profile"

# ---------- auto-login on the screen ----------
mkdir -p "$GETTY_DIR"
cat > "$GETTY_DIR/sanctuary-kiosk.conf" <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $KIOSK_USER --noclear %I \$TERM
EOF

# A desktop login screen would take over tty1; boot to the console instead (undone by --uninstall).
if systemctl is-enabled display-manager.service >/dev/null 2>&1; then
  info "A desktop login screen is installed; switching boot to console mode so the kiosk owns the screen"
fi
systemctl set-default multi-user.target >/dev/null

# ---------- optional daily reboot ----------
if [ -n "$REBOOT_AT" ]; then
  cat > "/etc/systemd/system/$REBOOT_UNIT.service" <<EOF
[Unit]
Description=Sanctuary Screens kiosk daily reboot
[Service]
Type=oneshot
ExecStart=/bin/systemctl reboot
EOF
  cat > "/etc/systemd/system/$REBOOT_UNIT.timer" <<EOF
[Unit]
Description=Sanctuary Screens kiosk daily reboot at $REBOOT_AT
[Timer]
OnCalendar=*-*-* $REBOOT_AT:00
[Install]
WantedBy=timers.target
EOF
  systemctl daemon-reload
  systemctl enable --now "$REBOOT_UNIT.timer" >/dev/null
  ok "Daily reboot scheduled at $REBOOT_AT"
fi

systemctl daemon-reload
ok "Kiosk installed. Reboot to start it:  sudo reboot"
echo "   Showing: $URL"
echo "   Change it: sudo nano $CONF   then reboot"
echo "   Remove it: sudo bash $0 --uninstall"
