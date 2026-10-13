# LexPubli — imagem única: o mesmo artefato roda o portal (gunicorn) e o worker.
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LEXPUBLI_STATIC_ROOT=/app/staticfiles \
    LEXPUBLI_MEDIA_ROOT=/data/media

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# collectstatic não precisa de banco nem de segredo real
RUN LEXPUBLI_SECRET_KEY=build LEXPUBLI_DEBUG=0 python manage.py collectstatic --noinput -v0

RUN useradd --system --uid 10001 --home /app lexpubli \
    && mkdir -p /data/media && chown -R lexpubli /data
USER lexpubli

EXPOSE 8000
CMD ["gunicorn", "lexpubli.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
