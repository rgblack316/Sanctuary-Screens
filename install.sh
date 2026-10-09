#!/usr/bin/env bash
# First-time install of Sanctuary Screens on the church NUC.
#   curl -fsSL https://raw.githubusercontent.com/rgblack316/Sanctuary-Screens/main/install.sh -o install.sh && bash install.sh
# Options (env vars): INSTALL_DIR (default /opt/sanctuary-screens), REPO_URL, BRANCH (default main)
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/rgblack316/Sanctuary-Screens.git}"
BRANCH="${BRANCH:-main}"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Use the repo this script lives in, otherwise clone into INSTALL_DIR.
if [ -z "${INSTALL_DIR:-}" ] && [ -f "$SELF_DIR/docker-compose.yml" ] && [ -d "$SELF_DIR/.git" ]; then
  INSTALL_DIR="$SELF_DIR"
fi
INSTALL_DIR="${INSTALL_DIR:-/opt/sanctuary-screens}"

bootstrap_common() {
  if [ -f "$INSTALL_DIR/scripts/common.sh" ]; then source "$INSTALL_DIR/scripts/common.sh"
  elif [ -f "$SELF_DIR/scripts/common.sh" ]; then source "$SELF_DIR/scripts/common.sh"
  else
    command -v git >/dev/null 2>&1 || { echo "git is required: sudo apt-get install -y git"; exit 1; }
    return 1
  fi
}

echo "Sanctuary Screens installer → $INSTALL_DIR"

# 1. Get the code
if [ -d "$INSTALL_DIR/.git" ]; then
  bootstrap_common || true
  info "Repository already present at $INSTALL_DIR"
else
  bootstrap_common || true
  command -v git >/dev/null 2>&1 || { echo "git is required: sudo apt-get install -y git"; exit 1; }
  if [ -e "$INSTALL_DIR" ] && [ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]; then
    echo "✘ $INSTALL_DIR exists and is not a Sanctuary Screens checkout. Choose another INSTALL_DIR." >&2; exit 1
  fi
  echo "==> Cloning $REPO_URL ($BRANCH)"
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
  source "$INSTALL_DIR/scripts/common.sh"
fi
cd "$INSTALL_DIR"
check_deps

# 2. Refuse to re-initialise an existing install
VOLUME="sanctuary-screens_mongo_data"
if [ -f .env ] && { docker volume inspect "$VOLUME" >/dev/null 2>&1 || [ -n "$("${DC[@]}" ps -q 2>/dev/null)" ]; }; then
  warn "An existing install was detected (.env and data volume '$VOLUME' are present)."
  echo "Nothing was changed. To update the app safely run:"
  echo "    cd $INSTALL_DIR && ./upgrade.sh"
  exit 0
fi

# 3. Directories
mkdir -p data/idle backups
ok "Data directories ready (data/idle for the idle slide image)"

# 4. Configuration
if [ -f .env ]; then
  ok "Keeping existing .env"
  merge_new_env_keys env.template .env
else
  [ -f env.template ] || die "env.template is missing from the repository – re-clone or pull the latest code."
  cp env.template .env
  chmod 600 .env
  if [ -n "${ADMIN_PIN:-}" ]; then
    [[ "$ADMIN_PIN" =~ ^[0-9]{4}$ ]] || die "ADMIN_PIN must be 4 digits"
    PIN="$ADMIN_PIN"
  else
    prompt_pin
  fi
  env_set ADMIN_PIN "$PIN" .env

  while true; do
    read -rp "App port [8091]: " APP_PORT_IN; APP_PORT_IN="${APP_PORT_IN:-8091}"
    [[ "$APP_PORT_IN" =~ ^[0-9]+$ ]] && [ "$APP_PORT_IN" -ge 1024 ] && [ "$APP_PORT_IN" -le 65535 ] || { warn "Use a number 1024-65535."; continue; }
    [ "$APP_PORT_IN" = "8080" ] && { warn "8080 is reserved for the other app."; continue; }
    port_in_use "$APP_PORT_IN" && { warn "Port $APP_PORT_IN is already in use."; continue; }
    break
  done
  env_set APP_PORT "$APP_PORT_IN" .env

  while true; do
    read -rp "Backend port [8092]: " BE_PORT_IN; BE_PORT_IN="${BE_PORT_IN:-8092}"
    [[ "$BE_PORT_IN" =~ ^[0-9]+$ ]] && [ "$BE_PORT_IN" != "$APP_PORT_IN" ] && [ "$BE_PORT_IN" != "8080" ] && [ "$BE_PORT_IN" -ge 1024 ] || { warn "Pick a different port."; continue; }
    port_in_use "$BE_PORT_IN" && { warn "Port $BE_PORT_IN is already in use."; continue; }
    break
  done
  env_set BACKEND_PORT "$BE_PORT_IN" .env

  read -rp "Currency symbol [\$]: " CUR_IN; CUR_IN="${CUR_IN:-\$}"
  env_set CURRENCY_SYMBOL "'$CUR_IN'" .env

  if command -v openssl >/dev/null 2>&1; then SECRET=$(openssl rand -hex 32); else SECRET=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'); fi
  env_set JWT_SECRET "$SECRET" .env
  ok "Created .env (edit later with: nano $INSTALL_DIR/.env)"
fi

APP_PORT=$(env_get APP_PORT .env)

# 5. Build and start
info "Building and starting containers (first build can take several minutes)…"
"${DC[@]}" up -d --build

# 6. Verify
if wait_healthy "$APP_PORT" 240; then
  print_urls "$APP_PORT"
  echo "The KJV translation is imported automatically on first start."
else
  "${DC[@]}" ps
  "${DC[@]}" logs --tail=40 backend frontend || true
  die "The app did not become healthy. Check the logs above, fix .env if needed, then run: ${DC[*]} up -d"
fi
