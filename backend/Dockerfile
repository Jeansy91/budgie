FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Apply pending security updates of the base image
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install the dependencies, then drop pip, setuptools and wheel: the runtime
# does not need them, and the copies bundled in the base image carry CVEs
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip setuptools wheel \
    && rm -rf /usr/local/lib/python3.13/site-packages/pip* \
        /usr/local/lib/python3.13/site-packages/setuptools* \
        /usr/local/lib/python3.13/site-packages/pkg_resources \
        /usr/local/lib/python3.13/site-packages/wheel* \
        /usr/local/lib/python3.13/ensurepip \
        /usr/local/bin/pip /usr/local/bin/pip3*

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

RUN useradd --system --uid 1000 budgie
USER budgie

EXPOSE 8000
# Database migrations run on every start, then the API starts
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
