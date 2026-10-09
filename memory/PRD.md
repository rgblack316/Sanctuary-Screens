# Sanctuary Screens – PRD

## Original problem statement
Church Display System POC – a fully local, Dockerized web app for the church Intel NUC with two separate live display functions: `/register` (attendance & offering display, current + exactly 7 days earlier, N/A if missing) and `/bible` (scripture display during sermons, one verse per slide, default idle slide, real-time updates). PIN-protected `/register-admin` and `/bible-admin` (one shared 4-digit PIN via env, hashed). Local Bible translation CSV import/delete/select (schema: translation, book, chapter, verse, text), KJV first, MongoDB storage with indexes, staging validation before commit, deletion safeguards (not live, not last). Prepared scripture list + ad-hoc lookup, manual text fallback, next/prev, clear-to-idle, WebSocket reconnect + resync. Docker Compose stack (frontend, backend, MongoDB), host networking, ports 8091/8092 (never 80/8080), MongoDB not on LAN, persistent volume. install.sh and upgrade.sh from GitHub (idempotent, never overwrite .env or delete data). README, .env.example. Full spec as provided by the user in the first message.

User choices: bundle public-domain KJV CSV and auto-import on first start; currency symbol from .env (default $); repo https://github.com/rgblack316/Sanctuary-Screens; preview PIN 1234; include cross-chapter ranges.

## Architecture
- backend/ FastAPI: server.py (PIN unlock + JWT per area, lockout, WS /api/ws/{register|bible}, startup indexes/migrations/PIN hash/KJV seed), register_routes.py, bible_routes.py, importer.py (CSV staging validation), reference.py (parser incl. cross-chapter), books.py (book normalisation), models.py
- frontend/ React: /, /register, /register-admin, /bible, /bible-admin; useLiveChannel (reconnect, heartbeat, HTTP fallback poll); fonts bundled locally (fontsource)
- Deploy: docker-compose.yml (mongo bridge on 127.0.0.1:27027; backend+nginx frontend host network), Dockerfiles, nginx template, .env.example, install.sh, upgrade.sh, scripts/common.sh, data/idle (idle image drop-in)

## User personas
- Service operator (Bible admin, runs slides during sermon)
- Counter/treasurer (enters attendance and offering)
- Congregation (views displays)
- Tech volunteer (installs/upgrades on NUC)

## Core requirements (static)
See original problem statement; acceptance criteria listed there.

## Implemented (2026-10-09)
- All four routes, PIN gate, register flow with exact 7-day comparison, Bible lookup/preview/edit/publish/next/prev/goto/clear/live translation switch, prepared list CRUD + reorder, translation import/validate/replace/delete/default, idle slide (env text or image in data/idle), WS live sync + reconnect
- Docker/compose/nginx, install.sh, upgrade.sh (--reset-pin, --no-pull), README
- Testing: iteration_1 – backend 39/39, frontend critical flows pass. Docker build/scripts only syntax-checked (no Docker in preview).

## Implemented (2026-10-09, iteration 2)
- User request: "We need to have the ability to customize the appearance on the /bible and /register screens. Being able to add in a background image and apply a parallax effect or blur to the images. We also need to be able to customize the colors used for the fonts on these displays. We need to have an admin panel to change the PIN as needed as well."
- /settings-admin (PIN area "settings"): per-display colors (background, text, accent, secondary, panel + opacity), background image upload stored in MongoDB (display_images), blur, darken/tint, parallax drift motion + speed; live iframe preview with sample content + portrait/landscape; save broadcasts via WS
- PIN change in UI (pin_version in JWT invalidates all other sessions); ADMIN_PIN env re-applies only when its value changes (fingerprint) or via upgrade.sh --reset-pin
- Testing: iteration_2 – 54/54 backend tests, frontend flows pass

## Implemented (2026-10-09, iteration 3)
- User request: "Add the ability in the settings to set a church name to be displayed. Add the ability to customize how that is displayed on both the register and bible displays as part of the other customizations."
- Church name (shared, site_settings) set in /settings-admin; per-display show/hide, 6 positions, size, color, all-caps; rendered on /register, /bible passage and idle slides; live preview + WS push
- Testing: iteration_3 – 68/68 backend tests, frontend flows pass

## Implemented (2026-10-09, iteration 4)
- User request: "Add an option to select a different date for the previous service attendance and offering in the case of a service that is cancelled, rescheduled, etc." + "Church Logo: Let admins upload a church logo that can sit beside the name on both displays"
- Register: per-service comparison override (comparison_service_date + comparison_overridden); admin "Compare with" selector (7 days earlier / another earlier recorded service)
- Church logo: shared upload (site_settings.logo_image_id, stored in display_images), per-display show + size, rendered beside the name at the name position (logo alone if no name)
- Testing: iteration_4 – 89/89 backend tests, frontend flows pass

## Implemented (2026-10-09, iteration 5)
- Bug fix: /bible idle slide overlapped church name with the accent bar. Idle now shows: logo (optional) → accent bar → "Welcome to" → church name (name color/caps settings) → today's date → optional subtitle. Falls back to "Welcome" + date when no name or name hidden.
- Testing: iteration_5 – all idle scenarios pass

## Implemented (2026-10-09, iteration 6)
- Removed accent line from idle welcome
- Renamed .env.example -> env.template (dot-files don't sync to GitHub from Emergent); install.sh/upgrade.sh/common.sh/README updated

## Implemented (2026-10-09, iteration 7)
- Bible slides: reference now above verse text (shrinks together); translation label position (6 spots) + show/hide toggle in Display Settings (Bible tab); slide counter bottom-right
- Testing: iteration_6 passed. Incident: older regression tests' teardown deleted the user's church name, logo and background image in the preview DB; destructive test files removed, user must re-upload.

## Implemented (2026-10-09, iteration 8)
- Scripture reference styling: Bible tab "Scripture reference" panel with color (accent_color) + size (reference_size 1-10); removed duplicate Reference row from Bible Colors panel
- Testing: iteration_7 passed (non-destructive; user settings preserved)

## Implemented (2026-10-09, iteration 9)
- Verse text size slider (verse_size 1-10, scales FitText base size; long verses still shrink to fit) in Bible tab "Scripture text & reference" panel
- Testing: iteration_8 passed (non-destructive; user settings preserved)

## Implemented (2026-10-09, iteration 10)
- Saved Looks per display (display_looks): save current tab settings + background under a name, apply (live WS push, "On screen" badge), update, delete; images referenced by looks are never deleted (release_image ref-check)
- Testing: iteration_9 passed. Incident: the test run removed the user's Bible background image (must be re-uploaded).

## Implemented (2026-10-09, iteration 11)
- Prepared scripture service date: calendar popover button (plus "Today") beside the typed date input (components/DatePicker.jsx)
- Register Admin service date: same calendar picker (DatePicker, testid service-date-*)
- Calendars mark recorded dates (green dot): GET /api/register/dates, GET /api/bible/prepared-dates; legend in popover
- Testing: iteration_10 passed (read-only)

## Backlog
- P1: Run install.sh on the real NUC and verify host networking, reboot persistence, offline use
- P1: Final idle slide design asset
- P2: backup.sh, reusable prepared templates, long-verse layout refinement, multi-operator conflict handling

## Next tasks
- On-NUC install validation; push repo to GitHub
