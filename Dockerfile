FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN python -m pip install --upgrade pip && pip install -r requirements.txt

COPY . /app

EXPOSE 5000
ENV GUNICORN_CMD_ARGS="--bind 0.0.0.0:5000 --workers 2 --threads 4 --timeout 60 --preload"

CMD ["gunicorn", "app:app"]

