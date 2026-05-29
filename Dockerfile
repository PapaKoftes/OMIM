FROM python:3.11-slim AS backend

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir .

# Copy source
COPY src/ src/
COPY data/ data/

EXPOSE 8000

CMD ["uvicorn", "omim.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- Frontend build ---
FROM node:20-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

# --- Production ---
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/
COPY data/ data/
RUN pip install --no-cache-dir .

# Copy frontend build
COPY --from=frontend-build /frontend/dist /app/static

EXPOSE 8000

CMD ["uvicorn", "omim.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
