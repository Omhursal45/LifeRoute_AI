# AI-Driven Emergency Ambulance Route Optimization System (LifeRoute AI)

Django + Django REST Framework backend, Bootstrap + Leaflet frontend, JWT authentication, SQLite for local development, and a PostgreSQL-ready database configuration. Routing uses the public **OSRM** service (OpenStreetMap data). Severity and prioritization use a **rule-based + weighted feature** engine (interpretable “pseudo-ML”) with optional user-reported severity.

**Disclaimer:** This is a demonstration system. For real emergencies, use your official emergency number.

---

## 1. Features

- **Users:** Patient, Driver, Admin roles; register/login; **JWT** (access + refresh).
- **Hospitals:** Name, coordinates, beds, emergency services; nearest-hospital API (haversine).
- **Ambulances:** Live lat/lon; driver can **PATCH** location; dashboard polls positions every **2 seconds** with **smooth marker animation** when coordinates change.
- **Hyderabad-only facilities:** Demo hospitals are real **Hyderabad** locations. **`/api/hospitals/nearest/`** returns only hospitals inside a **Hyderabad bounding box**, sorted by **min(distance from you, distance from nearest active ambulance)** so the list reflects either your position or fleet positions. GPS anchoring uses **`/api/emergency/demo/anchor-near-me/`**; if you are outside Hyderabad, anchors snap to the **city centre** so data stays in-region.
- **Emergency requests:** Symptoms → **AI severity** + **priority score**; suggested hospital + **OSRM** route (distance, duration) with a **mock rush-hour traffic** multiplier.
- **Mock SMS:** Logged to DB and console (`MockSMSLog`).
- **Dashboard:** Map, ambulances, hospitals, lists.
- **Admin:** Django `/admin/` + JSON **analytics** at `/api/emergency/analytics/` (admin JWT).
- **Bonuses:** Dark mode toggle, language switch (EN/ES scaffold via Django i18n), voice symptoms (Web Speech API, browser-dependent).

---

## 2. Step-by-step setup

### Prerequisites

- Python 3.11+ (tested on 3.13)
- (Optional) PostgreSQL for production-style DB
- (Optional) GNU gettext for `compilemessages` if you add full translations

### Create environment and install

```powershell
cd "path\to\LifeRoute AI"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Database and demo data

```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py seed_demo
```

### Run the server

```powershell
.\venv\Scripts\python.exe manage.py runserver
```

Open **http://127.0.0.1:8000/**.

### Demo accounts (after `seed_demo`)

| User      | Password   | Role    |
|-----------|------------|---------|
| `admin`   | `admin123` | Admin   |
| `driver1` | `driver123`| Driver  |
| `patient1`| `patient123`| Patient|

---

## 3. PostgreSQL (production-ready structure)

Set environment variables (no `POSTGRES_DB` → SQLite is used):

```text
POSTGRES_DB=liferoute
POSTGRES_USER=postgres
POSTGRES_PASSWORD=yourpassword
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DJANGO_SECRET_KEY=use-a-long-random-string
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=your.domain.com
```

Then run `migrate` again against Postgres.

---

## 4. API reference (summary)

Base URL: `http://127.0.0.1:8000`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register/` | No | Register (patient/driver only) |
| POST | `/api/auth/login/` | No | JWT obtain (access + refresh) |
| POST | `/api/auth/token/refresh/` | No | Refresh access token |
| GET | `/api/auth/me/` | JWT | Current user |
| GET/POST | `/api/hospitals/` | GET public; POST admin | List / create hospitals |
| GET/PATCH/DELETE | `/api/hospitals/<id>/` | GET public; write admin | Hospital detail |
| GET | `/api/hospitals/nearest/?lat=&lon=&limit=&consider_ambulances=1` | No | **Hyderabad bbox only**; each row includes `distance_km` (ranking score), `distance_km_from_you`, `distance_km_from_nearest_ambulance` |
| GET/POST | `/api/emergency/requests/` | JWT | List (role-filtered) / create request |
| GET/PATCH | `/api/emergency/requests/<id>/` | JWT | Detail; PATCH status/ambulance (admin/driver) |
| POST | `/api/emergency/routing/optimize/` | JWT | OSRM route + traffic factor |
| POST | `/api/emergency/routing/driver-navigate/` | JWT driver/admin | Body: `hospital_id` **or** `destination_latitude` + `destination_longitude`; optional `ambulance_id` (admin). Compares **OSRM alternatives** and returns the route with lowest **traffic-adjusted** score (demo). |
| GET | `/api/emergency/analytics/` | JWT admin | Counts / average severity |
| POST | `/api/emergency/demo/anchor-near-me/` | JWT | Body: `latitude`, `longitude` — moves **all** demo hospitals & ambulances near that point (dashboard uses this with your GPS) |
| GET | `/api/emergency/patient/live-tracking/?patient_lat=&patient_lng=` | JWT **patient** | Active request + **assigned ambulance** position; **road + straight-line distance**, **ETA**, route geometry (ambulance → you). See **`/track/`** page. |
| GET | `/api/tracking/ambulances/` | No | List ambulances |
| POST | `/api/tracking/ambulances/create/` | JWT admin | Create ambulance |
| PATCH | `/api/tracking/ambulances/<id>/location/` | JWT driver | Update position |

**Example: login**

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/auth/login/ -Method Post -ContentType "application/json" -Body '{"username":"patient1","password":"patient123"}'
```

**Example: create emergency (Bearer token)**

```powershell
$h = @{ Authorization = "Bearer YOUR_ACCESS_TOKEN"; "Content-Type" = "application/json" }
$body = '{"latitude":37.7749,"longitude":-122.4194,"symptoms":"chest pain and difficulty breathing","location_description":"Market St"}'
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/emergency/requests/ -Method Post -Headers $h -Body $body
```

---

## 5. Frontend pages

| URL | Purpose |
|-----|---------|
| `/` | Home |
| `/login/` | Login (stores JWT in `sessionStorage`) |
| `/register/` | Register |
| `/dashboard/` | Live map + ambulances + hospitals |
| `/emergency/` | Emergency request form + voice |
| `/admin-panel/` | Analytics cards (admin JWT) |
| `/admin/` | Django admin |

---

## 6. Tests

```powershell
.\venv\Scripts\python.exe manage.py test
```

---

## 7. UI overview (“screens”)

- **Home:** Hero, capability list, red **Request ambulance** CTA.
- **Dashboard:** Full-width Leaflet map, ambulance markers (red circles), hospital markers, side lists, **Simulate ambulance** (driver JWT).
- **Emergency:** Bootstrap form, geolocation, optional severity, JSON result panel.
- **Global:** Primary navbar, footer, **Dark** theme toggle, **EN/ES** language selector (add `.po/.mo` under `locale/` for real Spanish strings).

---

## 8. Project layout

```text
config/           # settings, urls, web views
accounts/         # User model, JWT, register
hospitals/        # Hospital CRUD + nearest
emergency/        # Requests, analytics, routing API, severity services
tracking/         # Ambulance + location updates
templates/pages/  # HTML templates
static/           # CSS, JS
```

---

## 9. OSRM and limits

The default `OSRM_BASE_URL` is the public demo (`https://router.project-osrm.org`). It is **rate-limited** and not for heavy production load. For production, host your own OSRM or use a commercial routing API and set `OSRM_BASE_URL` accordingly.

---

## 10. `manage.py` settings

This repo forces `DJANGO_SETTINGS_MODULE=config.settings` in `manage.py` so a stray environment variable does not point Django at another project.
