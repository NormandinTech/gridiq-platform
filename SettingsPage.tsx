version: "3.9"

# GridIQ Platform — Production Stack
# Deploy with: docker compose -f docker-compose.prod.yml up -d
#
# Services:
#   db        — TimescaleDB (PostgreSQL + time-series extension)
#   redis     — Cache + event pub/sub
#   api       — FastAPI backend
#   worker    — Background task worker (telemetry processing)
#   nginx     — Reverse proxy + SSL termination
#   frontend  — React dashboard (served as static files via nginx)

services:

  # ── TimescaleDB ─────────────────────────────────────────────────────────────
  db:
    image: timescale/timescaledb:latest-pg16
    container_name: gridiq-db
    restart: always
    environment:
      POSTGRES_DB:       ${DB_NAME:-gridiq_db}
      POSTGRES_USER:     ${DB_USER:-gridiq}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_HOST_AUTH_METHOD: scram-sha-256
    volumes:
      - gridiq_pgdata:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"     # localhost only — never expose to internet
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-gridiq} -d ${DB_NAME:-gridiq_db}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    deploy:
      resources:
        limits:
          memory: 2G

  # ── Redis ────────────────────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: gridiq-redis
    restart: always
    command: >
      redis-server
      --requirepass ${REDIS_PASSWORD}
      --appendonly yes
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
      --loglevel warning
    volumes:
      - gridiq_redis:/data
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── GridIQ API ───────────────────────────────────────────────────────────────
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    container_name: gridiq-api
    restart: always
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      APP_ENV:            production
      DEBUG:              "false"
      DATABASE_URL:       postgresql+asyncpg://${DB_USER:-gridiq}:${DB_PASSWORD}@db:5432/${DB_NAME:-gridiq_db}
      REDIS_URL:          redis://:${REDIS_PASSWORD}@redis:6379/0
      JWT_SECRET_KEY:     ${JWT_SECRET_KEY}
      SIMULATE_TELEMETRY: ${SIMULATE_TELEMETRY:-true}
      LOG_LEVEL:          INFO
      CORS_ORIGINS:       '["https://${DOMAIN}","https://www.${DOMAIN}"]'
    volumes:
      - gridiq_ml_models:/app/ml_models
      - gridiq_reports:/app/reports
    expose:
      - "8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
    deploy:
      resources:
        limits:
          memory: 2G
      replicas: 1

  # ── Nginx reverse proxy + SSL ─────────────────────────────────────────────
  nginx:
    image: nginx:1.27-alpine
    container_name: gridiq-nginx
    restart: always
    depends_on:
      - api
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deployment/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./deployment/nginx/sites:/etc/nginx/sites-enabled:ro
      - gridiq_frontend_build:/usr/share/nginx/html:ro
      - gridiq_ssl:/etc/letsencrypt:ro
      - gridiq_certbot_www:/var/www/certbot:ro

  # ── Certbot (auto SSL renewal) ────────────────────────────────────────────
  certbot:
    image: certbot/certbot:latest
    container_name: gridiq-certbot
    volumes:
      - gridiq_ssl:/etc/letsencrypt
      - gridiq_certbot_www:/var/www/certbot
    # Renews every 12 hours — certbot only acts when cert is within 30d of expiry
    entrypoint: >
      /bin/sh -c "trap exit TERM;
      while :; do
        certbot renew --webroot -w /var/www/certbot --quiet;
        sleep 12h & wait $${!};
      done"
    profiles:
      - ssl   # only run in production with real domain

volumes:
  gridiq_pgdata:
  gridiq_redis:
  gridiq_ml_models:
  gridiq_reports:
  gridiq_ssl:
  gridiq_certbot_www:
  gridiq_frontend_build:
