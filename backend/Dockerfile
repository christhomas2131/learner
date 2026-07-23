FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first (better layer caching).
COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY knowledge ./knowledge
RUN pip install --upgrade pip && pip install .

# Uploads + SQLite DB live on mounted volumes (see docker-compose).
RUN mkdir -p /data/uploads
ENV DATABASE_URL=sqlite+aiosqlite:////data/learner.db \
    UPLOAD_DIRECTORY=/data/uploads \
    MODEL_PROVIDER=none

EXPOSE 8000

# Apply migrations, then serve.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
