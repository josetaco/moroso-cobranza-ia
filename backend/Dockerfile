FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data

# Cloud Run inyecta la variable PORT (por defecto 8080)
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
