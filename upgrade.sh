#!/usr/bin/env bash
# Safe upgrade: pull latest code, keep .env and all data, rebuild, restart, verify.
#   ./upgrade.sh              normal upgrade (safe to re-run)
#   ./upgrade.sh --reset-pin  also set a new admin PIN (explicit only)
#   ./upgrade.sh --no-pull    rebuild/restart current code without pulling
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source scripts/common.sh

RESET_PIN=0; PULL=1; REEXEC=0
for arg in "$@"; do
  case "$arg" in
    --reset-pin) RESET_PIN=1 ;;
    --no-pull) PULL=0 ;;
    --reexec) REEXEC=1 ;;
    *) die "Unknown option $arg" ;;
  esac
done

[ -f .env ] || die "No .env found. This looks like a fresh machine – run ./install.sh first."
check_deps
BRANCH="${BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
PREV=$(git rev-parse HEAD)
STAMP=$(date +%Y%m%d-%H%M%S)

# 1. Back up configuration (data lives in the Docker volume and is never touched)
mkdir -p backups data/idle
cp -p .env "backups/.env.$STAMP"
ok "Backed up .env to backups/.env.$STAMP"

# 2. Pull latest code
if [ $PULL -eq 1 ] && [ $REEXEC -eq 0 ]; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    git status --short
    die "Local code changes found (listed above). Commit/stash them or run 'git checkout -- .' then re-run. Nothing was changed."
  fi
  SELF_SUM=$(sha1sum upgrade.sh scripts/common.sh | sha1sum)
  info "Pulling latest code ($BRANCH)…"
  git fetch origin "$BRANCH" || die "Could not reach GitHub. Nothing was changed."
  git merge --ff-only "origin/$BRANCH" || die "Could not fast-forward to origin/$BRANCH. Nothing was changed."
  if [ "$(git rev-parse HEAD)" = "$PREV" ]; then ok "Already on the latest version ($(git rev-parse --short HEAD))"
  else ok "Updated $(git rev-parse --short "$PREV") → $(git rev-parse --short HEAD)"; fi
  if [ "$(sha1sum upgrade.sh scripts/common.sh | sha1sum)" != "$SELF_SUM" ]; then
    info "Upgrade script changed – continuing with the new version"
    exec bash ./upgrade.sh --reexec "$@"
  fi
fi

# 3. Configuration: add new settings only, never overwrite existing ones
merge_new_env_keys env.template .env
if [ $RESET_PIN -eq 1 ]; then
  prompt_pin
  env_set ADMIN_PIN "$PIN" .env
  ok "Admin PIN updated (takes effect after restart)"
fi
APP_PORT=$(env_get APP_PORT .env)

# 4. Rebuild and restart (volumes are kept; never runs 'down -v')
info "Rebuilding images…"
"${DC[@]}" build --pull backend frontend || die "Build failed. The running app was not changed. Previous version: $PREV"
info "Restarting containers…"
"${DC[@]}" up -d --remove-orphans
# Database migrations and index updates run automatically when the backend starts.

# 5. Verify
if wait_healthy "$APP_PORT" 240; then
  docker image prune -f --filter "dangling=true" >/dev/null 2>&1 || true
  ok "Upgrade complete ($(git rev-parse --short HEAD))."
  print_urls "$APP_PORT"
else
  "${DC[@]}" ps
  "${DC[@]}" logs --tail=60 backend frontend || true
  echo
  echo "${c_err}✘ Upgrade finished but the app is not healthy.${c_off}"
  echo "Your data and .env are untouched. To go back to the previous version:"
  echo "    git checkout $PREV && ./upgrade.sh --no-pull"
  echo "Then return to the latest code later with: git checkout $BRANCH && ./upgrade.sh"
  exit 1
fi
