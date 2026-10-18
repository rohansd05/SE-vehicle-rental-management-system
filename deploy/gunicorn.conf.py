"""gunicorn for the django service of docker-compose.prod.yml (D1).

Mounted at /etc/gunicorn.conf.py. Only Caddy reaches port 8000, on the compose
network; it is never published on the VM.
"""

import multiprocessing

bind = "0.0.0.0:8000"
# OE-4's 4 vCPU host gives 9; a 2 vCPU VM gives 5 (each worker is one Postgres connection).
workers = multiprocessing.cpu_count() * 2 + 1
# bcrypt at 12 rounds (SE-2) and the PDF renders are CPU-bound; threads add little.
threads = 1
timeout = 60
graceful_timeout = 30
# Recycle workers now and then so a slow leak never grows for weeks.
max_requests = 1000
max_requests_jitter = 100
# Caddy is the only client, so its X-Forwarded-* headers are trusted.
forwarded_allow_ips = "*"
accesslog = "-"
errorlog = "-"
# The access log line has no query string or body, so no OTP or password reaches it (SE-2).
access_log_format = '%(h)s "%(m)s %(U)s %(H)s" %(s)s %(b)s %(L)ss'
