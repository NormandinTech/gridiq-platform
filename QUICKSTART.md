# GridIQ Platform — Multi-stage Dockerfile
# Stage 1: Build React frontend
# Stage 2: Production Python API image

# ── Stage 1: Frontend build ──────────────────────────────────────────────────
FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend

# Install dependencies first (layer caching)
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --silent

# Copy source and build
COPY frontend/ .
# Set production API URL — will be served from same domain via nginx
ENV VITE_API_URL=/api/v1
ENV VITE_WS_URL=wss://__DOMAIN__/api/v1
RUN npm run build
# Output is in /app/frontend/dist


# ── Stage 2: Production API ──────────────────────────────────────────────────
FROM python:3.12-slim AS production

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY scripts/  ./scripts/
COPY alembic.ini .
COPY config/   ./config/

# Copy built frontend into a known location so nginx can serve it
COPY --from=frontend-builder /app/frontend/dist ./frontend_dist/

# Create runtime directories
RUN mkdir -p ml_models reports/compliance logs

# Non-root user
RUN useradd -m -u 1000 gridiq \
    && chown -R gridiq:gridiq /app
USER gridiq

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Start command
CMD ["uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info", \
     "--access-log"]
