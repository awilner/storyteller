FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc default-libmysqlclient-dev pkg-config && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir gunicorn -r requirements.txt

COPY backend/ .
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000

CMD ["/entrypoint.sh"]
