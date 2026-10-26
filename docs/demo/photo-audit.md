# Vehicle photo audit (27 Oct 2026)

## Symptom

Vehicle photos do not show on the Veyora website in local development
(D3: Django runs natively, the frontend through `npm run dev`).

## Evidence

### 1. Processes and ports

`docker compose ps`: postgres (5434) and valkey (6379) healthy.

Ports 8000 and 5173 were already taken by **another project**:

```
127.0.0.1:8000  Listen  python  ...\Automated-Academic-Timetable-Scheduling-System\.venv\Scripts\uvicorn.exe ... --port 8000
::1:5173        Listen  node    ...\Automated-Academic-Timetable-Scheduling-System\frontend\...\vite.js
```

`manage.py runserver 8000` fails with "You don't have permission to access that
port", and Veyora's `npm run dev` falls back to `http://localhost:5174/`.
Runserver *can* bind `[::1]:8000` beside the uvicorn on `127.0.0.1:8000`, so
"localhost:8000" then means two different servers depending on IPv4 or IPv6.

### 2. Database and storage

```
settings: config.settings.development  DEBUG True
MEDIA_ROOT: ...\SE-vehicle-rental-management-system\backend\media (FileSystemStorage)
Vehicles: 42  VehiclePhotos: 168
sample: vehicles/photos/demo/MH02DB2001-front.jpg  (-rear, -left, -right, MH02DB2002-front)
missing on disk: 0
vehicles with 0 photos: none
MH03DX9002 -> id 40, Available, Powai
MH02DX8001 -> id 36, Available, Andheri
```

The data is complete; no file needs regenerating.

### 3. API

- `GET /api/v1/fleet/search/`: results carry **no photo field** (by design,
  `VehicleTile.tsx` B12: tiles show the bundled representative model or
  category photo).
- `GET /api/v1/fleet/vehicles/<id>/`: `photos` is a list of **absolute**
  signed links built from the request's Host header (`signed_file_url` →
  `request.build_absolute_uri`):

```
direct to runserver :8001   -> http://localhost:8001/api/v1/files/<token>/
through the Vite proxy      -> http://localhost:8000/api/v1/files/<token>/   (before the fix)
```

The Vite string shorthand `'/api': 'http://localhost:8000'` sets
`changeOrigin: true`, so Django sees `Host: localhost:8000` and links to the
backend's own origin. The browser then loads every `<img>` **directly from
localhost:8000, bypassing the proxy**, while all JSON goes through the proxy.

### 4. Fetching the photos

```
direct (runserver :8001)            vehicles 40, 36, 21: 200 image/jpeg (22-24 kB)
through Vite -> :8001               vehicles 40, 36, 21: 200 image/jpeg
headers: Cache-Control private, no-store; nosniff; no CSP/CORP that blocks <img>
```

Reproduced with the real repo config (Veyora on `[::1]:8000`, timetable
uvicorn on `127.0.0.1:8000`, Vite on 5174):

```
GET http://localhost:5174/api/v1/health/          -> {"status":"ok",...,"agency_name":"Veyora"}   (Node reaches ::1)
photo URL handed to the browser                   -> http://localhost:8000/api/v1/files/...
  curl -4 (localhost -> 127.0.0.1)                -> 404 application/json  (the timetable app)
  curl -6 (localhost -> ::1)                      -> 200 image/jpeg
```

So the page and its JSON work while every photo is a broken image. The
signature, salt, expiry and routing are all fine.

### 5. Frontend

- `features/booking/VehicleDetailPage.tsx`: `<img src={url}>` for each entry
  of `vehicle.photos`; matches the API (a list of URL strings).
- `features/search/VehicleTile.tsx`: `representativeImage(vehicle)` from
  `assets/vehicles/registry.ts`; all 27 registry ids exist in the manifest and
  `public/images/<id>/` and serve 200.
- `features/admin/VehiclePage.tsx`: `photo.url` from the admin serializer,
  same signed links.
- `public/sw.js` never caches `/api/`.

### 6. Tests (before the fix)

- `pytest apps/fleet apps/core`: green (part of the full run: 2198 passed).
- `npm test -- --run`: 7 failures, all multipart upload tests (MSW
  `ERR_ASSERTION` during handler lookup: fleet add, licence, handover, return,
  workshop invoice). They fail identically with the original `vite.config.ts`;
  none is about displaying photos.

### Production

`production.py` sets `SECURE_PROXY_SSL_HEADER` and `USE_X_FORWARDED_HOST`;
Caddy forwards the browser's host, so links read
`https://<SITE_HOSTNAME>/api/v1/files/...`, the same origin as the page. The
dev proxy problem does not exist there. The live server
(https://172-198-50-140.sslip.io) timed out on port 443 during this audit, so
it could not be checked.

## Root cause

Code/config, in development only. `frontend/vite.config.ts` proxied with the
string shorthand, which rewrites `Host` to `localhost:8000`. Django therefore
builds the absolute signed photo links to `http://localhost:8000`, and the
browser fetches images directly from there instead of through the proxy. On
this machine `localhost:8000` (IPv4) is another project's server, so the JSON
works and every photo 404s. The same links also break whenever the page is
not opened on the machine running Django.

## Fix

`frontend/vite.config.ts`: proxy with `{ target: 'http://localhost:8000',
changeOrigin: false }`. Django now sees the browser's host
(`localhost:5173`/`5174`) and builds the photo links to the page's own origin,
so they come back through the same proxy as the JSON. Backend behaviour for
documents, licences, handover photos, signatures and invoices is unchanged;
production is unchanged.

Test: `frontend/vite.config.test.ts` (fails before: the proxy was a bare
string; passes after).

After the fix (same failing setup), through Vite on 5174:

```
vehicle 40 Volkswagen Virtus (Powai, MH03DX9002):   4 x 200 image/jpeg  http://localhost:5174/api/v1/files/...
vehicle 36 Maruti Suzuki Wagon R (Andheri, MH02DX8001): 4 x 200 image/jpeg
vehicle 21 Maruti Suzuki Baleno (Andheri):          4 x 200 image/jpeg
vehicle 22 Hyundai Venue (Andheri):                 4 x 200 image/jpeg
/admin/login/ 200, /static/admin/css/base.css 200, /api/v1/auth/login/ 200
```
