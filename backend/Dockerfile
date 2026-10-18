# Django, the Celery worker and Celery Beat (D1): one image, three commands in
# docker-compose.prod.yml. Runtime requirements only; the debug toolbar and the
# other development packages (requirements-dev.txt) are never installed.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# A non-root user owns the media and static folders, so the named volumes mounted
# there start out writable by it.
RUN useradd --uid 1000 --create-home vrms \
    && mkdir -p /app/media /app/staticfiles \
    && chown vrms:vrms /app/media /app/staticfiles
USER vrms

EXPOSE 8000
CMD ["gunicorn", "-c", "/etc/gunicorn.conf.py", "config.wsgi"]
