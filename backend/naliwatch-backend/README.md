# NaliWatch backend

NaliWatch tracks every load of septic waste from the household to an authorized treatment plant, and uses citizen reports and health signals to decide which tanks to empty first. This repo is the backend for the MVP described in the NaliWatch Product and Build Plan.

**Stack:** Python 3.11, FastAPI, SQLAlchemy 2, PostgreSQL + PostGIS, Redis + Celery, OR-Tools (routing), scikit-learn (DBSCAN), Claude API (report triage), WhatsApp Cloud API / Telegram (reporting bots).

**Design rule:** an AI model is used only where the input is messy human content (photos, text, voice transcripts). Routes, volumes, due dates, scoring and verification are plain code, so every decision is repeatable and auditable.

---

## 1. Quick start

### With Docker (recommended)
```bash
cp .env.example .env              # set JWT_SECRET; add ANTHROPIC_API_KEY for AI triage
docker compose up -d --build      # db (PostGIS), redis, api, worker, beat
docker compose exec api python -m scripts.seed --reset
docker compose exec api python -m scripts.simulate_trip --mode matched
```
Interactive API docs: http://localhost:8000/docs  ·  health check: `GET /healthz`

### Without Docker
1. Install Postgres 16 with PostGIS and Redis, create a database and user.
2. `python -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `cp .env.example .env` and fix `DATABASE_URL` / `REDIS_URL`.
5. `python -m scripts.seed --reset` then `uvicorn app.main:app --reload`
6. In two more terminals (needed for scheduled jobs):
   `celery -A app.workers.celery_app.celery worker -l info` and
   `celery -A app.workers.celery_app.celery beat -l info`

### Tests
```bash
pytest          # 15 tests, pure logic, no database needed
```

### Demo logins
`scripts.seed` creates one demo ward ("Ward 12 (demo)", coordinates around Pune; change them for your pilot ward), 40 tanks, one operator with two vehicles and two drivers, one plant, one hotspot (5 overflow reports + 2 sickness counts), and these users. Login is phone OTP; with `OTP_DEV_ECHO=true` the API returns the code in the response so you can log in without an SMS provider.

| Role | Phone |
|---|---|
| admin | +919000000001 |
| officer (Ward 12) | +919000000002 |
| operator manager | +919000000003 |
| drivers | +919000000004, +919000000005 |
| plant staff | +919000000006 |
| ASHA worker | +919000000007 |
| reporter | +919000000008 |

`OTP_DEV_ECHO` and `ENV=dev` are for local use only. Turn both off in production (`ENV=prod` also hides the `/dev/*` helper routes).

---

## 2. Project layout

```
app/
  main.py            FastAPI app, router registration, startup table creation
  config.py          all settings (env vars), including the open decisions
  db.py              engine, sessions, init_db (creates PostGIS extension + tables)
  models.py          all tables
  schemas.py         request bodies
  serializers.py     response shaping (what each role is allowed to see)
  deps.py            auth dependency, role checks, ward scoping, RLS session vars
  security.py        JWT, OTP hashing, phone normalisation
  kv.py              Redis helpers (rate limits, daily AI cap)
  events.py          publishes live updates for /ws/live
  audit.py           audit-log helper
  geo.py             PostGIS/shapely helpers, ward lookup
  routers/           HTTP + WebSocket endpoints (one file per area)
  services/          business logic (see section 4)
  workers/           Celery app, schedule and tasks
scripts/
  seed.py            demo data
  simulate_trip.py   end-to-end trip simulator against a running API
tests/               unit tests for prediction, priority, clustering, routing, verification
sql/rls_example.sql  opt-in database-level access rules
```

---

## 3. Roles and what each can do

| Role | Channel | Can do | Cannot see |
|---|---|---|---|
| household | mobile web / WhatsApp | register tanks (with consent), request a pump-out, cancel own jobs, send reports | other people's tanks or jobs |
| reporter | WhatsApp / Telegram | send reports (location + photo, voice note or text) | anything except own reports |
| asha | WhatsApp | add sickness counts for an area | any patient-level data (counts only) |
| operator | web dashboard | accept or decline offered jobs, plan trips, manage own vehicles and drivers | reporter identity, other operators |
| driver | mobile web app | start own trip (GPS consent), send GPS points, confirm each stop with an OTP, finish collection | other drivers' trips, anything not assigned today |
| plant | tablet / web | see tankers heading to their plant, confirm each load and its volume | the pumped volume (kept hidden so measurement is independent) |
| officer | web dashboard | map, reports, flags, KPIs, scheduling triggers, review and decide flags | other wards |
| admin | web dashboard | everything, plus create wards, plants, operators, assign roles, read the audit log | n/a |

Access is enforced in the API on every endpoint. `sql/rls_example.sql` shows how to repeat the main rules inside Postgres (opt-in, see section 11).

---

## 4. How the pieces work

### End-to-end flow
```
Intake -> Prioritise -> Schedule -> Route -> Pump-out -> Drive to plant -> Plant check -> Verified | Flag
```
1. **Intake.** A household registers a tank, or anyone sends a report. Reports go through `services/intake.py`.
2. **Prioritise.** `services/prediction.py` computes a due date per tank and a priority score with the reasons stored alongside it.
3. **Schedule.** `services/scheduling.py` offers each pending job to a certified, active operator that has a vehicle and a driver (least loaded first). The operator accepts or declines (a declined job is never re-offered to the same operator).
4. **Route.** `services/routing.py` batches the operator's accepted jobs into trips with OR-Tools, using road distances from OSRM (straight-line x1.3 if OSRM is down). Each trip starts at the operator depot and ends at the nearest authorized plant. Vehicle capacity is enforced; if capacity is short, the lowest-priority jobs are left unrouted and returned in `unrouted_job_ids`.
5. **Pump-out.** The driver starts the trip (must accept GPS consent), sends GPS points, and at each tank asks for an OTP that goes to the household. The household reads it out; the driver submits it with the litres pumped. A confirmed stop completes the job and resets that tank's last-emptied date and due date.
6. **Plant check.** Plant staff confirm the received litres. `services/verification.py` decides the result.
7. **Result.** A trip is `verified` only if it entered an authorized plant geofence inside its time window and the received volume is within tolerance of the pumped volume. Anything else creates a flag for a ward officer. Reports linked to a verified trip are marked resolved.

### Report intake (`services/intake.py`)
- Rate limited per user (`REPORT_RATE_LIMIT_PER_HOUR`, default 10).
- Voice notes are transcribed (`services/stt.py`) and the raw audio is never stored.
- Photos are re-encoded (this removes EXIF/GPS metadata), classified by Claude, faces are blurred before storage, and photos showing the inside of a home are rejected. If the classifier says a face is visible but the detector cannot find it, the photo is dropped entirely and the report is kept.
- Classification uses forced structured output: type (`overflow`, `dumping`, `manual_cleaning`, `other`), severity 1 to 3, confidence, a short reason (stored for audit), and an English summary. A daily call cap (`AI_DAILY_CALL_CAP`) and a keyword fallback keep it safe when the API is down, capped, or not configured.
- Reports below `AI_CONFIDENCE_THRESHOLD` (default 0.5) go to the officer review queue (`needs_review`) and create no job until an officer confirms.
- Duplicates (same type within `DEDUPE_RADIUS_M` and `DEDUPE_HOURS`) are stored but marked `duplicate` and left out of clusters and jobs.
- Overflow and dumping reports create a job; dumping and manual-cleaning reports also create a flag. **Manual cleaning is an emergency regardless of AI confidence:** flag + urgent job (priority 1000) + immediate operator offer + a message to `MANUAL_CLEANING_RESPONDER_PHONE` with a map link.
- Reporter identity is never included in job or trip responses, so operators and drivers cannot see who reported.

### Due-date estimator and priority ranker (`services/prediction.py`)
```
due date = last emptied + capacity * fill limit / (occupants * sludge per person per day)
```
Priority score (higher = sooner), each rule recorded in `priority_reason`:
- overdue tank: 40 + 0.5 per overdue day (max 60 days); due within 30 days: up to +30
- open overflow report nearby: up to +30 by severity, plus +1 per day open (max +10)
- inside a risk zone (failures and sickness overlap): +15; watch zone: +7
- manual cleaning report: 1000 (always first)

### Cluster engine (`services/clustering.py`)
DBSCAN (haversine, `CLUSTER_EPS_M` = 150 m, `CLUSTER_MIN_SAMPLES` = 3) over open failure reports from the last 30 days and sickness counts from the last 14 days (weighted by case count). A cluster containing both is a **risk** zone; reports alone make a **watch** zone. Recomputed every 15 minutes and whenever a sickness count is added.

### Verification rule (`services/verification.py`)
A trip is flagged for the first of these reasons that applies (all reasons are stored in the flag's detail):
`plant_not_authorized`, `no_confirmed_stops`, `outside_time_window`, `volume_mismatch`, `no_gps_trail`, `gps_gap_unverified`, `no_geofence_entry`, and (from the nightly checker) `plant_skipped`.
- Volume tolerance is the larger of `VOLUME_TOLERANCE_PCT` of the pumped volume and `VOLUME_TOLERANCE_MIN_LITRES`.
- GPS gaps longer than `GPS_GAP_MINUTES` are checked **before** blaming a driver: if the trail never enters the plant geofence but has gaps, the reason is `gps_gap_unverified`, not `no_geofence_entry`.
- The system never penalises an operator. An officer reviews every flag and decides `confirmed`, `dismissed` (the trip becomes `closed_reviewed`) or `needs_more_info`.

### Chat bot (`services/bot_core.py`, `routers/bot.py`)
One flow for WhatsApp and Telegram. A person shares a location and sends a photo, voice note or text in any order; the report is created as soon as both a location and some evidence are present. Replies are bilingual (English/Hinglish). Commands: `/start`, `/cancel`. ASHA workers share a location, then send `sick <count> <symptoms>` (for example `sick 4 fever diarrhoea`).
- Telegram: set the webhook to `POST /bot/telegram` with `secret_token` equal to `TELEGRAM_WEBHOOK_SECRET`.
- WhatsApp: callback URL `/bot/whatsapp`, verify token `WHATSAPP_VERIFY_TOKEN`. If `WHATSAPP_APP_SECRET` is set, request signatures are verified.

### Background jobs (`workers/`)
| Task | Schedule (Asia/Kolkata) | What it does |
|---|---|---|
| recompute_clusters | every 15 min | rebuilds risk/watch zones |
| refresh_predictions_and_jobs | 02:00 daily | recomputes due dates, creates jobs for tanks due within 14 days, rescores the job queue |
| run_scheduler | every 30 min | offers pending jobs to operators |
| check_overdue_trips | every 15 min | flags trips past their time window with no plant confirmation |
| send_reminders | 17:00 daily | tells households their pump-out is tomorrow |
| purge_retention | 03:30 daily | deletes old GPS trails and report photos |

---

## 5. API reference

All endpoints except `/auth/*`, `/public/stats`, `/healthz` and the bot webhooks need `Authorization: Bearer <token>`. Full request/response schemas are in `/docs`.

**Auth**
- `POST /auth/otp/request` {phone} · `POST /auth/otp/verify` {phone, otp, name?, language?, consent?} -> token · `GET /auth/me`

**Tanks** (household, operator, officer)
- `POST /tanks` (consent required; staff register on behalf with `owner_phone`) · `GET /tanks` · `GET /tanks/{id}` · `PATCH /tanks/{id}` · `GET /tanks/by-qr/{code}`

**Reports and health**
- `POST /reports` (multipart: lat, lng, text, photo, audio) · `GET /reports` · `PATCH /reports/{id}` (officer: change type/severity/status, add note)
- `POST /health-signals` (asha, officer) · `GET /health-signals` (officer)

**Jobs and priority**
- `POST /jobs` (request pump-out) · `GET /jobs` · `POST /jobs/{id}/accept|decline|cancel`
- `POST /jobs/refresh` · `POST /jobs/run-scheduler` · `GET /priority/tanks` (officer)

**Trips and drivers**
- `POST /trips/plan` · `GET /trips` · `GET /trips/{id}`
- `POST /trips/{id}/start` {consent_gps} · `POST /trips/{id}/gps` (batch of up to 500 points) · `POST /trips/{id}/finish`
- `POST /trips/{id}/stops/{stop_id}/otp` · `POST /trips/{id}/stops/{stop_id}/confirm` {otp, volume_pumped_litres, lat?, lng?}

**Plant**
- `GET /plant/expected` · `POST /plant/disposals` {trip_id, volume_received_litres}

**Flags and KPIs**
- `GET /flags` · `GET /flags/{id}` · `POST /flags/{id}/decision` {decision, note?}
- `GET /metrics/kpis`: the five pilot targets (on-schedule %, verified-drop %, flags reviewed within 24 h, manual-cleaning dispatch under 2 h, report-to-resolution days)

**Map and public**
- `GET /map/layers` (GeoJSON: tanks, reports, clusters, plants, active trips, open flags) · `GET /public/stats` (no login: ward-level counts and hotspots rounded to a ~1 km grid, never names or exact addresses)
- `WS /ws/live?token=<JWT>`: live report, trip and GPS events for officers (own ward) and admins

**Admin and setup**
- `POST /admin/users` · `POST /admin/wards` (GeoJSON) · `POST /admin/plants` (GeoJSON polygon geofence) · `GET /admin/audit-log`
- `POST|GET /operators` · `PATCH /operators/{id}` · `POST /operators/{id}/vehicles` · `POST /operators/{id}/drivers` · `GET /plants`

**Bots and dev**
- `POST /bot/telegram` · `GET|POST /bot/whatsapp`
- `POST /dev/flag-skipped`, `POST /dev/recluster` (admin, `ENV=dev` only)

### First-time setup order for a real pilot
1. Admin creates the ward (`POST /admin/wards`), the plant with its geofence (`POST /admin/plants`), the operator (`POST /operators`) and staff users (`POST /admin/users` with role, ward, operator_id or plant_id).
2. The operator adds vehicles and drivers.
3. Households register tanks (or operators and officers register them during pump-outs and put the QR code on the tank).
4. Celery beat then creates jobs, schedules, and recomputes clusters on its own.

---

## 6. Data model

`users`, `wards`, `properties`, `tanks`, `reports`, `health_signals`, `clusters`, `operators`, `vehicles`, `drivers`, `plants`, `jobs`, `trips`, `trip_stops`, `gps_points`, `disposals`, `flags`, `audit_log`.

Three chains: tank -> job -> trip (via trip_stops) -> disposal; reports and health signals feed priority and clusters; flags attach to trips and reports. All locations are PostGIS geometry (SRID 4326). Health signals are counts for an area with no patient identity. `audit_log` records changes and views of trips, flags and household tanks.

---

## 7. Configuration

Everything is an environment variable (see `.env.example` for the full list). The important groups:

- **Core:** `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES`, `CORS_ORIGINS`, `ENV`, `OTP_DEV_ECHO`
- **AI:** `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `AI_DAILY_CALL_CAP`, `AI_CONFIDENCE_THRESHOLD`
- **Speech to text:** `STT_PROVIDER` (`whisper`, `bhashini`, `none`), `OPENAI_API_KEY`
- **Channels:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`, `SMS_WEBHOOK_URL`
- **Storage:** `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_REGION`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` (leave `S3_BUCKET` empty to store media under `MEDIA_DIR` locally)
- **Routing:** `OSRM_URL` (the default is the public demo server; use your own for production)

### Decisions the plan leaves open (placeholders, set with your team)
| Decision | Setting | Default |
|---|---|---|
| Volume tolerance for a mismatch | `VOLUME_TOLERANCE_PCT`, `VOLUME_TOLERANCE_MIN_LITRES` | 10% and 100 L (larger of the two) |
| Fill limit and sludge per person | `FILL_LIMIT`, `SLUDGE_LITRES_PER_PERSON_DAY` | 0.33 and 0.15 (not from local guidance: replace) |
| Named human responder for manual cleaning | `MANUAL_CLEANING_RESPONDER_PHONE` | empty, so no page is sent until set |
| GPS ping interval and gap that counts as a flag | `GPS_PING_INTERVAL_SECONDS`, `GPS_GAP_MINUTES` | 30 s and 10 min |
| OTP delivery when the household has no WhatsApp | code tries WhatsApp/Telegram, then SMS | printed code on the QR plate is not built |
| Retention for photos, audio and GPS trails | `RETENTION_PHOTO_DAYS`, `RETENTION_GPS_DAYS` | 180 and 90 days; raw voice is never stored |

Also configurable: `TRIP_WINDOW_HOURS` (default 12), `DEFAULT_JOB_LITRES`, `CLUSTER_EPS_M`, `CLUSTER_MIN_SAMPLES`.

---

## 8. Security and privacy built in

- Phone OTP login (hashed codes, 5-minute expiry, request and attempt limits), short-lived JWTs, role checks on every endpoint, ward scoping for officers.
- Per-request Postgres session variables (`app.user_id`, `app.role`, `app.ward`) for optional row-level security.
- Stop OTPs are hashed, expire in 15 minutes, and allow 5 attempts.
- Consent is required when a household registers a tank and when a driver starts a shift with GPS on.
- Faces blurred, EXIF stripped, home-interior photos rejected, raw voice never stored, retention purge job, health data as area counts only.
- Public page shows only ward-level counts and hotspots on a coarse grid.
- Webhook checks: Telegram secret token, WhatsApp verify token and optional HMAC signature.
- Hold data in an Indian cloud region and put the API behind HTTPS in production.

---

## 9. Deploying

- API and worker run from the same image (`Dockerfile`); run one `beat` instance only.
- Use a managed Postgres with PostGIS in an Indian region (for example Supabase or AWS RDS in Mumbai) and a managed Redis.
- Set `ENV=prod`, `OTP_DEV_ECHO=false`, a long random `JWT_SECRET`, and a real S3-compatible bucket.
- Add Sentry, uptime checks and daily backups (with a tested restore), as the plan requires.
- Add Alembic migrations before the pilot; tables are currently created at startup.

---

## 10. Troubleshooting

- **`extension "postgis" is not available`:** use a PostGIS image/server (the compose file uses `postgis/postgis:16-3.4`).
- **Photo upload returns 500 about `CascadeClassifier`:** you have OpenCV 5.x; install `opencv-python-headless>=4.9,<5` (already pinned in `requirements.txt`) and uninstall any other `opencv-*` package.
- **Routes look straight-line:** OSRM was unreachable, so distances fell back to straight-line x1.3. Check `OSRM_URL`.
- **No jobs appear:** run `POST /jobs/refresh` (or wait for the 02:00 task); jobs are created only for tanks due within 14 days. The seed does this once.
- **Jobs stay `pending`:** an operator needs an active status, a valid certification date, at least one active vehicle and one active driver.
- **Reports all go to `needs_review`:** `ANTHROPIC_API_KEY` is not set or the daily cap was reached (the keyword fallback still catches manual cleaning).
- **`simulate_trip` says no planned trip:** each trip is used once; run it with `--driver +919000000005` for the other driver, or re-seed.

---

## 11. Limitations

- **Bhashini** speech-to-text is a stub (Whisper works). Claude does not transcribe audio.
- **SMS** uses a generic JSON webhook; the Indian DLT registration and provider adapter are yours to add. WhatsApp messages outside the 24-hour window need approved templates (`wa_send_template` exists but is not wired to events).
- `sql/rls_example.sql` is an opt-in starting point, not tested against every flow. Use a non-owner database role for the API, or RLS is bypassed.
- The WebSocket feed notices a closed connection only on the next event.
- Not in the MVP (as in the plan): online payments, sensor hardware, enforcement actions, native mobile apps, multi-city tenancy.
- Have a lawyer confirm DPDP Act 2023 consent wording, the manual-scavenging escalation process, and state rules for operator licensing and disposal sites before go-live.

## 12. What has been tested

15 unit tests (due-date formula, priority rules, clustering, routing, verification rules) plus an end-to-end run on real PostGIS and Redis: seed, scheduling, routing with the OSRM fallback, OTP stop confirmation, GPS trail, plant confirmation in all three outcomes (verified, volume mismatch, plant skipped), flag review, the emergency report path, duplicate detection, role blocking and the chat flow.

**Not tested:** live Claude calls, real Telegram/WhatsApp webhooks, S3, Celery beat, a live OSRM server, the WebSocket feed.
