#!/usr/bin/env bash
# Shared helpers for install.sh / upgrade.sh
set -euo pipefail

c_ok=$'\e[32m'; c_warn=$'\e[33m'; c_err=$'\e[31m'; c_dim=$'\e[2m'; c_off=$'\e[0m'
info() { echo "${c_dim}==>${c_off} $*"; }
ok()   { echo "${c_ok}✔${c_off} $*"; }
warn() { echo "${c_warn}!${c_off} $*"; }
die()  { echo "${c_err}✘ $*${c_off}" >&2; exit 1; }

check_deps() {
  local missing=()
  for cmd in git docker curl; do command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd"); done
  if [ ${#missing[@]} -gt 0 ]; then
    echo "Missing required tools: ${missing[*]}"
    echo "On Ubuntu/Debian:  sudo apt-get update && sudo apt-get install -y git curl"
    echo "Docker Engine + Compose plugin: https://docs.docker.com/engine/install/"
    die "Install the missing tools and re-run."
  fi
  if docker compose version >/dev/null 2>&1; then DC=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1; then DC=(docker-compose)
  else die "Docker Compose not found. Install the docker-compose-plugin package."; fi
  docker info >/dev/null 2>&1 || die "Cannot talk to Docker. Start Docker or run with sudo / add your user to the 'docker' group."
  if command -v systemctl >/dev/null 2>&1 && ! systemctl is-enabled docker >/dev/null 2>&1; then
    warn "Docker is not enabled at boot. Run: sudo systemctl enable docker"
  fi
}

env_get() { # env_get KEY FILE
  local line; line=$(grep -E "^$1=" "$2" | tail -n1 || true)
  line="${line#*=}"; line="${line%\'}"; line="${line#\'}"; line="${line%\"}"; line="${line#\"}"
  echo "$line"
}

env_set() { # env_set KEY VALUE FILE  (replaces or appends one line)
  local tmp; tmp=$(mktemp)
  if grep -qE "^$1=" "$3"; then
    awk -v k="$1" -v v="$2" 'BEGIN{FS=OFS="="} $1==k {print k"="v; next} {print}' "$3" > "$tmp"
  else
    cp "$3" "$tmp"; printf '%s=%s\n' "$1" "$2" >> "$tmp"
  fi
  cat "$tmp" > "$3"; rm -f "$tmp"
}

merge_new_env_keys() { # add keys present in env.template but missing from .env, never overwrite
  [ -f "$1" ] || { warn "$1 not found – skipping new-settings check"; return 0; }
  local example="$1" target="$2" added=0
  while IFS= read -r line; do
    [[ "$line" =~ ^[A-Z_][A-Z0-9_]*= ]] || continue
    local key="${line%%=*}"
    if ! grep -qE "^${key}=" "$target"; then printf '%s\n' "$line" >> "$target"; info "Added new setting $key to .env"; added=1; fi
  done < "$example"
  [ $added -eq 0 ] && ok ".env already has all settings"
  return 0
}

port_in_use() { # true if something other than our app is listening
  if command -v ss >/dev/null 2>&1; then ss -ltnH "sport = :$1" 2>/dev/null | grep -q .; else return 1; fi
}

prompt_pin() {
  local p1 p2
  while true; do
    read -rsp "Admin PIN (4 digits): " p1; echo
    [[ "$p1" =~ ^[0-9]{4}$ ]] || { warn "PIN must be exactly 4 digits."; continue; }
    read -rsp "Confirm PIN: " p2; echo
    [ "$p1" = "$p2" ] && { PIN="$p1"; return; }
    warn "PINs did not match."
  done
}

wait_healthy() { # wait_healthy PORT TIMEOUT_SECONDS
  local port="$1" limit="${2:-180}" waited=0
  info "Waiting for the app to report healthy on port $port (up to ${limit}s)…"
  while [ $waited -lt "$limit" ]; do
    if curl -fsS "http://127.0.0.1:${port}/api/health" >/dev/null 2>&1; then
      ok "Health check passed: $(curl -fsS "http://127.0.0.1:${port}/api/health")"
      return 0
    fi
    sleep 3; waited=$((waited + 3))
  done
  return 1
}

print_urls() {
  local port="$1" ips
  ips=$(hostname -I 2>/dev/null || true)
  echo
  echo "Sanctuary Screens is running. Open on the church LAN:"
  for ip in $ips; do
    [[ "$ip" == *:* ]] && continue
    echo "  Register display : http://${ip}:${port}/register"
    echo "  Register admin   : http://${ip}:${port}/register-admin"
    echo "  Bible display    : http://${ip}:${port}/bible"
    echo "  Bible admin      : http://${ip}:${port}/bible-admin"
    echo
  done
  [ -z "$ips" ] && echo "  http://<this-machine-ip>:${port}/register  (and /register-admin, /bible, /bible-admin)"
}
