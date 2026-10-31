# Hosted build: FastAPI serves the React app from one URL, with Spark off (so no Java).

FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app/backend
ENV USE_SPARK=false PYTHONUNBUFFERED=1

# pyspark and py4j go unused with Spark off, and pywin32 has no Linux build.
COPY backend/requirements.txt ./
RUN grep -vE '^(pyspark|py4j|pywin32)==' requirements.txt > requirements.docker.txt \
    && pip install --no-cache-dir -r requirements.docker.txt \
    && rm requirements.docker.txt

COPY backend/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist

# --forwarded-allow-ips trusts the host's TLS proxy, so the app sees https and sets a Secure cookie.
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --forwarded-allow-ips='*'"]
