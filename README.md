# Sanctuary Screens

Local church display system for the Intel NUC. Two independent live displays on the church LAN:

| Route | Purpose |
|---|---|
| `/register` | Attendance & offering display (this week + exactly 7 days earlier) |
| `/register-admin` | PIN-protected entry of service numbers |
| `/bible` | Scripture display – one verse per slide; also reference-only slides and custom slides (hymns, announcements); idle slide when nothing is live |
| `/bible-admin` | PIN-protected scripture/custom slide control, prepared list per service date, slide library, hymn shortcut, translation import/delete |
| `/settings-admin` | PIN-protected church name & logo, display appearance (backgrounds, colors, sizes, layout), saved Looks, backups, admin PIN change |

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
sudo bash install.sh            # installs to /opt/sanctuary-screens (main branch)
# test a different branch:  sudo BRANCH=dev bash install.sh
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

See `env.template` (the installer copies it to `.env`; the template is not a dot-file so it always syncs to GitHub). Set `JWT_SECRET` to a random value (the installer does this; or `openssl rand -hex 32`) - if it is a placeholder or under 32 characters the backend logs a warning and uses a random secret that ends admin sessions at every restart. Key settings: `ADMIN_PIN` (4 digits, shared by both admin pages), `APP_PORT`, `BACKEND_PORT`, `CURRENCY_SYMBOL`, `IDLE_TITLE`, `IDLE_SUBTITLE`, `MONGO_IMAGE` (use `mongo:4.4` if the CPU lacks AVX). After editing run `docker compose up -d`.

The PIN is stored in the database only as a bcrypt hash. Five wrong PIN attempts lock the device out for 5 minutes; each repeated lockout doubles the wait (up to 24 hours), and a correct PIN resets it. Admin sessions last 12 hours per browser.

`ADMIN_PIN` sets the PIN on first start. After that the PIN can be changed in `/settings-admin` → Admin PIN; that change survives restarts and upgrades (changing it signs out all other admin screens). `ADMIN_PIN` only takes effect again if you change its value in `.env` (or run `./upgrade.sh --reset-pin`) – use this to recover a forgotten PIN.

## Display appearance

`/settings-admin` has a tab per display (`/bible`, `/register`) with a live preview (landscape/portrait, optional sample content):

- church name and logo (shown at the top or bottom of both displays and on the idle slide)
- colors: background, main text, accent, secondary text, panel/tile color and opacity
- background image upload (PNG/JPG/WEBP/GIF, max 12 MB, stored in MongoDB so it is kept through upgrades)
- blur, darken/tint, and a slow "parallax drift" motion with adjustable speed
- Bible layout: scripture reference size/color (separate from verse text), verse text size nudge, translation label show/hide and position (top/bottom, left/center/right)
- **Saved Looks**: save the current style under a name (e.g. "Easter", "Christmas") and apply it again with one click

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

Bible display tip: in `/settings-admin` → Bible → *Church name & logo*, tick **Hide on verse & custom slides** to show the church name only on the idle slide. The background image (including the parallax drift) stays continuous when switching between the idle slide and verses instead of restarting.

## Reference formats

`Romans 6:23`, `Rom 6:23-25`, `Psalm 23`, `John 3:16-4:2` (cross-chapter), `John 3-4`, `1 Jn 1:9,10`, `Romans 6:23; 8:1`. Every verse becomes its own slide (max 300 per passage). If a lookup fails, use the Manual text tab – blank lines separate slides. Tick **Reference only** on the lookup tab to show just the reference (e.g. `John 3:16-18`) on a single slide, without the verse text.

## Custom slides, hymns & slide library

- **Custom slide** tab (Compose panel): a title plus optional text – no scripture lookup. A line containing only `---` starts a new slide (e.g. a set of announcements stepped through with Next/Prev). The title uses the Scripture Reference style and the text uses the Verse Text style; no translation label is shown.
- **Hymn shortcut** (same tab): enter title and page and pick a hymnal → title line `Amazing Grace`, text `Page 312` with the hymnal name below. Hymnal names are saved for the drop-down (add / delete them there) and the last one used is remembered.
- **Save to prepared list** adds whatever is in the preview (scripture, reference only, manual text, hymn or custom slide) to the service date selected in the Prepared panel. The Prepared panel is split into **Scripture**, **Hymns** and **Custom** lists (tabs with counts); each list scrolls and has its own Move up/down. The Add dialog opens on the active tab.
- **Save to library** keeps a slide for reuse (e.g. Welcome, Offering, Doxology). In the **Slide library** panel each saved slide has Preview, Go live, Add to the selected service date, Edit (rename or change its content) and Delete. Editing a library slide also updates the copies already added to service dates.
- The library has a search box, Scripture / Hymn / Custom filters and pages of 25 (**Load more**). While you build a slide, matching library slides are suggested ("Use" or "Add to date"), and **Save to library** is disabled if a slide with that name already exists, so you don't create duplicates.

## Hymnal lookup (CSV import)

`/bible-admin` → **Songbooks** panel. Import a CSV with the columns `songbook,title,page` (optional `number`). Use **Download sample** for a template, **Validate** to check a file first, and choose **Replace** or **Add** when importing. In the Hymn tab, type a page or song number (or part of a title); if several songs share a page you get a list to pick from. Songbook names are added to the hymnal drop-down automatically. Songs are included in backups.

## Bible preview

`/bible-preview` (open on the LAN like `/bible`, no PIN) mirrors what you are building in `/bible-admin` – the current draft and the slide you select – with a "Preview · not on screen" badge. Nothing reaches `/bible` until you press **Send to screen**.

## Operating during a service

- `/bible-admin`: pick a prepared item or library slide (Preview / Go live) or type a reference, check the slide-by-slide preview (each slide is editable), then **Send to screen**. Use Prev/Next, the verse chips, or arrow keys / PageUp / PageDown (works with presentation clickers). Switch translation live from the On Screen bar. **Clear to idle** returns `/bible` to the idle slide.
- `/register-admin`: choose the service date on the calendar (dates with records are marked), enter attendance and offering, **Publish to display**. Previous week defaults to the record from exactly 7 days earlier and can be overridden with another date; if none exists the display shows `N/A`. Saving the same date again updates that record; an accidentally created date can be deleted from the history list.
- Both admin calendars mark dates that already have data (register records / prepared items).

Displays reconnect automatically after a backend restart or network blip and re-sync the current state.

## Display kiosks (auto-start Chromium)

Run this once on each display machine (Ubuntu, Ubuntu Server, Debian or Raspberry Pi OS; no desktop needed). It installs a minimal X + Chromium, creates a locked-down `kiosk` user that auto-logs in on the screen, and opens the display full screen on boot. Chromium waits until the NUC answers, restarts itself if it crashes, and the screen never blanks or shows a cursor.

```bash
curl -fsSL https://raw.githubusercontent.com/rgblack316/Sanctuary-Screens/main/kiosk/setup-kiosk.sh -o setup-kiosk.sh
sudo bash setup-kiosk.sh --server <nuc-ip> --display bible      # or --display register
sudo reboot
```

Options: `--url <full url>`, `--port 8091`, `--rotate left|right|inverted` (portrait screens), `--reboot-at 04:00` (daily reboot), `--uninstall`. Run without options to be prompted. To change what a screen shows, edit `/etc/sanctuary-kiosk.conf` and reboot. SSH still works normally for maintenance. If the machine had a desktop login screen, it now boots to console mode (`--uninstall` restores it).

## Backups

`/settings-admin` → **Backups** tab:
- **Back up now** and a weekly automatic backup (choose day, time and how many to keep). Backups are gzip files in the `backups/` folder of the install (mounted into the backend), containing register records, translations, prepared lists, slide library, hymnal names, display settings, looks and images (not the PIN).
- Download, delete or restore any backup, or restore from an uploaded backup file (restore replaces current data – confirm required; the file is checked first, a safety backup of your current data is taken automatically, and it is put back if the restore fails).
- Optional email of each backup using your own SMTP account (e.g. Gmail: `smtp.gmail.com`, port 587, STARTTLS, Google app password). The SMTP password is stored encrypted (the key comes from `JWT_SECRET` in `.env`, so changing `JWT_SECRET` means re-entering it); a username/password is not accepted with security set to "none". Use **Send test email** to check. Email needs internet on the NUC; local backups do not.
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
backend/    FastAPI app (server.py, bible_routes.py, library_routes.py, register_routes.py, appearance*.py, looks_routes.py, backup*.py, importer.py, reference.py, books.py), Dockerfile, seed/kjv.csv
frontend/   React app, Dockerfile, nginx/default.conf.template
docker-compose.yml  env.template  install.sh  upgrade.sh  scripts/common.sh
data/idle/  optional idle slide image (mounted read-only into the backend)
```
