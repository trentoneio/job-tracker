# Multi-arch base so a Raspberry Pi can build and run it natively (arm64).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data

WORKDIR /code

# Pinned deps first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Container entrypoint: brief root fixup of the bind-mounted data volume,
# then a permanent drop to the dedicated non-root user.
COPY entrypoint.py /entrypoint.py

# Dedicated system account for the long-running server process. Nologin shell;
# owns /app/data so SQLite (WAL) + uploads stay writable when it runs non-root.
RUN groupadd -r jobtracker \
    && useradd -r -g jobtracker -s /sbin/nologin jobtracker \
    && mkdir -p /app/data \
    && chown -R jobtracker:jobtracker /app/data

EXPOSE 8000

# The slim base image ships no curl, so the healthcheck uses the Python stdlib.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz')"]

# No USER directive on purpose: the entrypoint starts as root for a few seconds
# to adopt the host's data directory (Docker creates it root-owned when missing),
# then setuids permanently and execs uvicorn — `ps` always shows jobtracker.
ENTRYPOINT ["python", "/entrypoint.py"]
