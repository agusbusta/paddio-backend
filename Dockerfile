# Paddio API - imagen para Azure Container Apps (o cualquier PaaS con contenedor)
FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema para psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# App Runner usa puerto 8080 por defecto
ENV PORT=8080
EXPOSE 8080

# Gunicorn + Uvicorn worker (producción)
CMD gunicorn app.main:app \
    --workers 1 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT} \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
