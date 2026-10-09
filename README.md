# Sanctuary Screens

Local church display system for the Intel NUC. Two independent live displays on the church LAN:

| Route | Purpose |
|---|---|
| `/register` | Attendance & offering display (this week + exactly 7 days earlier) |
| `/register-admin` | PIN-protected entry of service numbers |
| `/bible` | Scripture display – one verse per slide, idle slide when nothing is live |
| `/bible-admin` | PIN-protected scripture control, prepared list, translation import/delete |
| `/settings-admin` | PIN-protected display appearance (background image, blur, parallax drift, colors) and admin PIN change |

Everything runs locally in Docker (React + FastAPI + MongoDB). No internet is needed during a service; scripture is looked up from translations imported into the local database. KJV is bundled and imported automatically on first start.

## Ports & networking

| Component | Network | Port | Reachable from |
|---|---|---|---|
| frontend (nginx) | host | `8091` (`APP_PORT`) | church LAN |
| backend (FastAPI) | host | `8092` (`BACKEND_PORT`) | `127.0.0.1` only by default (`BACKEND_BIND=0.0.0.0` for LAN access) |
| mongodb | bridge | `27027` (`MONGO_HOST_PORT`) | `127.0.0.1` only – never the LAN |

Ports 80 and 8080 are never used, so the app runs alongside the other Docker project. Because the app containers use host networking they share the NUC's IP – reserve that IP in DHCP and point the kiosk browsers at `http://<nuc-ip>:8091/register` or `/bible`.

## Install (first time)

Requirements: Git, Docker Engine and the Docker Compose plugin (the script checks and tells you what is missing).

```bash
curl -fsSL https://raw.githubusercontent.com/rgblack316/Sanctuary-Screens/main/install.sh -o install.sh
sudo bash install.sh            # installs to /opt/sanctuary-screens
# or: git clone https://github.com/rgblack316/Sanctuary-Screens.git && cd Sanctuary-Screens && ./install.sh
```

The installer clones the repo, creates `data/idle`, creates `.env` from `env.template`, asks for the admin PIN, app/backend ports and currency symbol, generates a session secret, builds and starts the stack, waits for the health check and prints the LAN URLs. If it detects an existing install it stops without changing anything and points you to `upgrade.sh`.

## Upgrade

```bash
cd /opt/sanctuary-screens && sudo ./upgrade.sh
```

- backs up `.env` to `backups/`, pulls with fast-forward only, adds any new settings from `env.template` without overwriting yours
- rebuilds images and restarts; the MongoDB volume (register history, translations, prepared lists) is never deleted
- database migrations / index updates run automatically when the backend starts
- verifies health and prints success, or prints logs plus the exact rollback command
- safe to re-run. Options: `--reset-pin` (set a new PIN), `--no-pull` (rebuild current code)

## Configuration (`.env`)

See `env.template` (the installer copies it to `.env`; the template is not a dot-file so it always syncs to GitHub). Key settings: `ADMIN_PIN` (4 digits, shared by both admin pages), `APP_PORT`, `BACKEND_PORT`, `CURRENCY_SYMBOL`, `IDLE_TITLE`, `IDLE_SUBTITLE`, `MONGO_IMAGE` (use `mongo:4.4` if the CPU lacks AVX). After editing run `docker compose up -d`.

The PIN is stored in the database only as a bcrypt hash. Five wrong PIN attempts lock the device out for 5 minutes. Admin sessions last 12 hours per browser.

`ADMIN_PIN` sets the PIN on first start. After that the PIN can be changed in `/settings-admin` → Admin PIN; that change survives restarts and upgrades (changing it signs out all other admin screens). `ADMIN_PIN` only takes effect again if you change its value in `.env` (or run `./upgrade.sh --reset-pin`) – use this to recover a forgotten PIN.

## Display appearance

`/settings-admin` has a tab per display (`/bible`, `/register`) with a live preview (landscape/portrait, optional sample content):

- colors: background, main text, accent, secondary text, panel/tile color and opacity
- background image upload (PNG/JPG/WEBP/GIF, max 12 MB, stored in MongoDB so it is kept through upgrades)
- blur, darken/tint, and a slow "parallax drift" motion with adjustable speed

Saving pushes the change to the open displays instantly.

## Idle slide

`/bible` shows the idle slide on start-up and whenever the display is cleared. By default it shows `IDLE_TITLE` / `IDLE_SUBTITLE`. To use a designed slide, drop one image (`.png/.jpg/.webp/.svg`) into `data/idle/` – it is picked up live, no rebuild needed.

## Bible translations (CSV)

One translation per UTF-8 CSV file with this header:

```csv
translation,book,chapter,verse,text
KJV,Genesis,1,1,In the beginning God created the heaven and the earth.
KJV,1 John,1,9,"If we confess our sins, he is faithful and just to forgive us our sins..."
```

Optional columns: `book_abbrev`, `testament`, `reference`. Book names are normalised (e.g. `I John`, `1John`, `1 John` → `1 John`; `Psalm` → `Psalms`). The whole file is validated first (missing columns, non-integer chapter/verse, empty text, duplicate verses, multiple translation codes); nothing is written unless validation passes. Re-importing an installed code requires ticking “Replace existing”, which swaps the data in atomically.

A translation can't be deleted while it is on the live display or if it is the last one installed.

## Reference formats

`Romans 6:23`, `Rom 6:23-25`, `Psalm 23`, `John 3:16-4:2` (cross-chapter), `John 3-4`, `1 Jn 1:9,10`, `Romans 6:23; 8:1`. Every verse becomes its own slide (max 300 per passage). If a lookup fails, use the Manual text tab – blank lines separate slides.

## Operating during a service

- `/bible-admin`: pick a prepared scripture (Preview / Go live) or type a reference, check the verse-by-verse preview (each slide is editable), then **Send to screen**. Use Prev/Next, the verse chips, or arrow keys / PageUp / PageDown (works with presentation clickers). Switch translation live from the On Screen bar. **Clear to idle** returns `/bible` to the idle slide.
- `/register-admin`: choose the service date, enter attendance and offering, **Publish to display**. Previous week is always the record from exactly 7 days earlier; if none exists the display shows `N/A`. Saving the same date again updates that record.

Displays reconnect automatically after a backend restart or network blip and re-sync the current state.

## Backups

`/settings-admin` → **Backups** tab:
- **Back up now** and a weekly automatic backup (choose day, time and how many to keep). Backups are gzip files in the `backups/` folder of the install (mounted into the backend), containing register records, translations, prepared scripture, display settings, looks and images (not the PIN).
- Download, delete or restore any backup, or restore from an uploaded backup file (restore replaces current data – confirm required).
- Optional email of each backup using your own SMTP account (e.g. Gmail: `smtp.gmail.com`, port 587, STARTTLS, Google app password). Use **Send test email** to check. Email needs internet on the NUC; local backups do not.
- The schedule uses the NUC's local time (`/etc/localtime` is mounted into the backend).

## Useful commands

```bash
docker compose ps                 # status
docker compose logs -f backend    # backend logs
docker compose restart            # restart everything
docker compose down               # stop (data is kept; never add -v)
```

## Repository layout

```
backend/    FastAPI app (server.py, bible_routes.py, register_routes.py, importer.py, reference.py, books.py), Dockerfile, seed/kjv.csv
frontend/   React app, Dockerfile, nginx/default.conf.template
docker-compose.yml  env.template  install.sh  upgrade.sh  scripts/common.sh
data/idle/  optional idle slide image (mounted read-only into the backend)
```
