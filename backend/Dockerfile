FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ARG REQUIREMENTS=prod
COPY requirements/ requirements/
RUN pip install -r requirements/${REQUIREMENTS}.txt

RUN useradd --create-home --uid 1000 app
COPY --chown=app:app . .
RUN mkdir -p /app/staticfiles /data/media && chown -R app:app /app/staticfiles /data
USER app

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
