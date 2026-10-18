# Deploying Veyora on one Azure VM

This is the production layout settled in **D1**: one Ubuntu VM running Docker
Compose with PostgreSQL 16, Valkey, Django on gunicorn, a Celery worker,
Celery Beat and Caddy. Caddy gets the HTTPS certificate automatically (CO-1),
serves the React app (the PWA of **D8**) and Django's static files, and
forwards `/api` and `/admin` to Django. Traceability: `docs/traceability-deploy.md`.

| File | What it is |
|---|---|
| `docker-compose.prod.yml` | The six services, their health checks and volumes |
| `backend/Dockerfile` | The image for Django, the worker and Beat (runtime packages only) |
| `frontend/Dockerfile` | Builds the React app and copies it into the Caddy image |
| `deploy/Caddyfile` | HTTPS, security headers, what is served and what is forwarded |
| `deploy/gunicorn.conf.py` | gunicorn settings for the `django` service |
| `deploy/backup.sh` | Nightly database and media backup, kept for 7 days |
| `backend/.env` | Every setting, read by all services (never committed) |

> **Course demo.** The payment gateway and the e-mail/SMS service stay on the
> **mock** (sandbox) implementations in `integrations/` in production too
> (`PAYMENT_GATEWAY_BACKEND=mock`, `NOTIFICATION_BACKEND=mock`), as CO-7 allows.
> No real card is charged and no real message is sent; the worker logs the
> messages instead.

All commands below run on the VM, in the repository folder, unless they start
with `az` (run those on your own computer with the Azure CLI).

---

## 1. Create the VM

- Image: **Ubuntu Server 22.04 LTS** (OE-4).
- Size: OE-4 asks for **4 vCPU and 8 GB RAM**, for example `Standard_B4als_v2`
  or `Standard_F4s_v2`. A smaller size (for example `Standard_B2s`, 2 vCPU and
  4 GB) runs the demo but is a deviation from OE-4; record it as proposal
  N4-P1 in `docs/decisions.md` if you use one.
- Disk: 30 GB or more.
- Networking: a **static** public IP address (so the host name below does not
  change when the VM is stopped and started), and inbound rules for ports
  **22** (SSH, your own IP only), **80** and **443** (TCP) and **443** (UDP, HTTP/3).
  Port 80 must stay open: Let's Encrypt checks it before issuing the certificate.

The host name is the public IP address with dashes, under sslip.io (a free
wildcard DNS name, no DNS set-up needed). For IP `20.40.60.80`:

```
SITE_HOSTNAME=20-40-60-80.sslip.io
```

## 2. Install Docker (Ubuntu 22.04)

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"   # then log out and back in once
docker compose version             # must print v2.x
```

## 3. Clone the repository

```bash
cd ~
git clone https://github.com/rohansd05/SE-vehicle-rental-management-system.git
cd SE-vehicle-rental-management-system
```

## 4. Create `backend/.env`

```bash
cp backend/.env.example backend/.env
chmod 600 backend/.env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # use as SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(24))"       # use as POSTGRES_PASSWORD
python3 -c "import secrets; print(secrets.token_hex(24))"       # use as PAYMENT_WEBHOOK_SECRET
nano backend/.env
```

The same file is read by Django, the worker, Beat, PostgreSQL and Caddy. Set
every line as below (`<host>` is your `SITE_HOSTNAME`). Never commit this file
and never reuse the development values.

| Variable | Production value | Read by |
|---|---|---|
| `SECRET_KEY` | the long random string generated above | Django (also signs the 15-minute file links, SI-3) |
| `DEBUG` | `False` | Django |
| `ALLOWED_HOSTS` | `<host>` | Django |
| `CSRF_TRUSTED_ORIGINS` | `https://<host>` | Django |
| `NUM_PROXIES` | `1` (Caddy) | client IP for throttling, the audit log and django-axes |
| `DATABASE_URL` | `postgres://vrms:<POSTGRES_PASSWORD>@postgres:5432/vrms` | Django |
| `REDIS_URL` | `redis://valkey:6379/0` | Django cache, Celery broker and results |
| `AGENCY_NAME` | `Veyora` (D24) | API and UI |
| `CURRENCY` | `INR` | API |
| `AGENCY_TAX_REGISTRATION` | the GSTIN to print on invoices (may stay empty for the demo) | invoices (Pay.Invoice) |
| `PAYMENT_GATEWAY_BACKEND` | `mock` | integrations (sandbox, see the note above) |
| `PAYMENT_GATEWAY_KEY_ID`, `PAYMENT_GATEWAY_KEY_SECRET` | empty (unused by the mock) | integrations |
| `PAYMENT_WEBHOOK_SECRET` | a random string generated above (SI-1.4) | the webhook signature check |
| `NOTIFICATION_BACKEND` | `mock` | integrations (sandbox) |
| `SMS_ACCOUNT_SID`, `SMS_AUTH_TOKEN` | empty (unused by the mock) | integrations |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | keep the example values (unused while `NOTIFICATION_BACKEND=mock`) | Django mail |
| `MEDIA_URL_EXPIRY_SECONDS` | `900` (SI-3) | signed file links |
| `SECURE_HSTS_SECONDS` | `31536000` | Django HSTS header |
| `SITE_HOSTNAME` | `<host>`, e.g. `20-40-60-80.sslip.io` | Caddy (certificate), the Django health check |
| `POSTGRES_DB` | `vrms` | PostgreSQL (first start only) |
| `POSTGRES_USER` | `vrms` | PostgreSQL (first start only) |
| `POSTGRES_PASSWORD` | the random password generated above, the same as in `DATABASE_URL` | PostgreSQL (first start only) |

Business rules (refund limit, grace periods, deposits and the rest) are
constants in `backend/config/settings/business_rules.py` and are not read from
the environment.

## 5. Start the stack

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps        # postgres, valkey and django "healthy"
docker compose -f docker-compose.prod.yml logs -f caddy   # watch the certificate being issued
```

On every start the `django` service runs `migrate` and `collectstatic`, then
gunicorn. The worker and Beat start only once Postgres and Valkey are healthy
and Django is healthy (so the migrations have run). Open
`https://<host>/` and `https://<host>/api/v1/health/` (it must answer
`"status": "ok"`).

## 6. First deploy only: demo data and the administrator

Run these **once**, in this order, right after the first start:

```bash
docker compose -f docker-compose.prod.yml exec django python manage.py seed_demo
docker compose -f docker-compose.prod.yml exec django python manage.py seed_demo --reports
docker compose -f docker-compose.prod.yml exec django python manage.py createsuperuser
```

- `migrate` has already run (step 5). `seed_demo` loads the demo branches,
  fleet, tariffs, accounts and maintenance jobs (and writes the generated demo
  photos to the media volume); `seed_demo --reports` adds three months of past
  bookings for the Reports screen and the Rate Vehicle demo. Run `--reports`
  **exactly once**, after `seed_demo`.
- `createsuperuser` asks for the e-mail, name, mobile number and password of
  your own Administrator (it gets the Administrator role and Django admin
  access). Use a strong password; it is never shown again.
- The demo accounts (`admin@vrms.test` and the others in `README.md`, password
  `Demo@1234`) are public knowledge. They are meant for the course demo; change
  their passwords (Django admin, `/admin/`) if the site stays up afterwards.

**This database can never be reset.** Ledger entries, invoices, credit and
debit notes, the audit log and signed condition reports are append-only (the
database refuses to change or delete them), so `seed_demo --reset` refuses once
`--reports` has run. To start over you must delete the Postgres volume, which
deletes **all** data:

```bash
docker compose -f docker-compose.prod.yml down
docker volume rm veyora_postgres_data veyora_media   # everything is gone after this
docker compose -f docker-compose.prod.yml up -d
# then step 6 again
```

## 7. Scheduled tasks (Celery Beat)

Beat uses the `django_celery_beat` **DatabaseScheduler**, so the schedules are
rows the migrations created; nothing else needs setting up. They are listed
(and can be paused) in the Django admin under "Periodic tasks".

| Task | Schedule | Registered by | Requirement |
|---|---|---|---|
| `apps.bookings.tasks.release_expired_holds` "Release expired booking holds" | every 1 minute | `bookings/migrations/0003_schedule_hold_release.py` | Book.Hold.Expire |
| `apps.bookings.tasks.declare_no_shows` "Declare no-shows" | every 1 minute | `bookings/migrations/0005_schedule_no_show.py` | Appendix B No-show, BR-8 (R2) |
| `apps.notifications.tasks.send_pickup_reminders` "Send pickup reminders" | every 5 minutes | `notifications/migrations/0002_schedule_pickup_reminder.py` | Notify.Remind (R3) |
| `apps.maintenance.tasks.raise_preventive_jobs` "Raise due preventive jobs" | every 1 day | `maintenance/migrations/0004_schedule_daily_alerts.py` | BR-15, Maint.Auto.Time (N3) |
| `apps.maintenance.tasks.alert_expiring_documents` "Alert expiring vehicle documents" | every 1 day | `maintenance/migrations/0004_schedule_daily_alerts.py` | SA-3 (N3) |

The daily tasks run first when Beat first starts, then every 24 hours from
then on (an interval, not a fixed clock time).

## 8. Update after a `git pull`

```bash
cd ~/SE-vehicle-rental-management-system
git pull
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d     # restarts what changed; django runs migrate first
docker compose -f docker-compose.prod.yml ps
docker image prune -f                               # remove the old images
```

To run the migrations by hand (for example to see their output):

```bash
docker compose -f docker-compose.prod.yml exec django python manage.py migrate
docker compose -f docker-compose.prod.yml restart worker beat
```

## 9. Backups (nightly, 7 days)

`deploy/backup.sh` writes a `pg_dump` of the database (custom format) and a
tar of the media volume (photos, signatures, workshop invoices) to
`/var/backups/veyora`, and deletes backups older than 7 days.

```bash
sudo mkdir -p /var/backups/veyora && sudo chown "$USER" /var/backups/veyora
sh deploy/backup.sh          # once by hand to check it works
crontab -e                   # then add the line below
```

```
15 2 * * * sh /home/azureuser/SE-vehicle-rental-management-system/deploy/backup.sh >> /home/azureuser/veyora-backup.log 2>&1
```

(02:15 UTC is 07:45 IST; change `azureuser` to your user name.) The backups
stay on the same VM, so they do not survive losing the VM; copy them elsewhere
(for example `scp` to your computer) before deleting the VM.

### Restore a backup

A restore goes into a fresh, empty database (the append-only rows cannot be
overwritten in place):

```bash
cd ~/SE-vehicle-rental-management-system
STAMP=20261024T021500Z                                   # the backup to restore
docker compose -f docker-compose.prod.yml down
docker volume rm veyora_postgres_data veyora_media
docker compose -f docker-compose.prod.yml up -d postgres
docker compose -f docker-compose.prod.yml exec -T postgres \
  sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error' \
  < /var/backups/veyora/vrms-$STAMP.dump
docker compose -f docker-compose.prod.yml run --rm -T --no-deps django \
  tar xzf - -C /app/media < /var/backups/veyora/media-$STAMP.tar.gz
docker compose -f docker-compose.prod.yml up -d
```

Do not run `seed_demo` after a restore; the data is already there.

## 10. Stop and start the VM (to save credit)

A stopped and **deallocated** VM costs nothing for compute (the disk and the
static IP still cost a little). The containers restart by themselves when the
VM boots (`restart: unless-stopped` and the Docker service is enabled).

```bash
az vm deallocate --resource-group <resource-group> --name <vm-name>   # stop
az vm start      --resource-group <resource-group> --name <vm-name>   # start
```

Stopping from the Azure portal ("Stop") deallocates too. Shutting down from
inside the VM (`sudo poweroff`) does **not** deallocate, and the VM is still
billed. With a static IP the host name and the certificate stay valid.

## 11. Install the app on a phone (D8, OE-2)

- Android (Chrome): open `https://<host>/`, menu, **Install app**.
- iPhone (Safari): open `https://<host>/`, Share, **Add to Home Screen**.

The service worker caches only the app shell and static files (never `/api`,
`/admin` or `/media`); without a connection the app shows its offline page.

## 12. When something is wrong

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail 100 django worker beat caddy
docker compose -f docker-compose.prod.yml exec django python manage.py check --deploy
```

- No certificate: check that ports 80 and 443 are open in the Azure network
  security group and that `SITE_HOSTNAME` matches the VM's public IP.
- `400 Bad Request` from Django: `ALLOWED_HOSTS` must be exactly `SITE_HOSTNAME`.
- A sign-in or a form refused with "CSRF": `CSRF_TRUSTED_ORIGINS` must be
  `https://<host>`.
- The worker prints the mock e-mails and SMS (including one-time passwords) in
  its log: `docker compose -f docker-compose.prod.yml logs -f worker`.
