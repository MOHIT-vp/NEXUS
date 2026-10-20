FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for asyncpg, python-magic, and health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY . .

# Expose backend API port
EXPOSE 8000

# Run migrations, seed reference data, and start server
CMD ["sh", "-c", "PYTHONPATH=. alembic upgrade head && PYTHONPATH=. python -m scripts.seed_reference_data && PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8000"]

