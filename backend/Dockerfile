FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
RUN chmod +x /app/entrypoint.sh \
    && DJANGO_DEBUG=true python manage.py collectstatic --noinput \
    && useradd --create-home --uid 1000 gradapp \
    && chown -R gradapp:gradapp /app
USER gradapp

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
# gthread workers keep idle browser connections from blocking request handling.
# PORT is set by hosting platforms such as Render; WEB_CONCURRENCY sets the worker count.
CMD ["sh", "-c", "exec gunicorn gradapp.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --worker-class gthread --threads 4 --timeout 180"]
