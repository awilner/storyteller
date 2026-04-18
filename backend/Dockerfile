FROM python:3.14-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc default-libmysqlclient-dev pkg-config && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        pandoc texlive-latex-base texlive-fonts-recommended texlive-latex-extra lmodern calibre && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir daphne -r requirements.txt

COPY . .
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000

CMD ["/entrypoint.sh"]
