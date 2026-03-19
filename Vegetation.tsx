version: "3.9"

# GridIQ Platform — Full local stack
# Run: docker compose up -d
# API will be available at http://localhost:8000
# Docs at http://localhost:8000/docs

services:

  # ── PostgreSQL + TimescaleDB ──────────────────────────────────────────────
  db:
    image: timescale/timescaledb:latest-pg16
    container_name: gridiq-db
    restart: unless-stopped
    environment:
      POSTGRES_DB: gridiq_db
      POSTGRES_USER: gridiq
      POSTGRES_PASSWORD: gridiq_dev_password
    ports:
      - "5432:5432"
    volumes:
      - gridiq_pgdata:/var/lib/postgresql/data
      - ./scripts/sql/init_timescale.sql:/docker-entrypoint-initdb.d/01_init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U gridiq -d gridiq_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── Redis (cache + pub/sub event bus) ────────────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: gridiq-redis
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    volumes:
      - gridiq_redis:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── Apache Kafka (production telemetry ingestion) ─────────────────────────
  zookeeper:
    image: confluentinc/cp-zookeeper:7.6.0
    container_name: gridiq-zookeeper
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    volumes:
      - gridiq_zk_data:/var/lib/zookeeper/data

  kafka:
    image: confluentinc/cp-kafka:7.6.0
    container_name: gridiq-kafka
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092,PLAINTEXT_INTERNAL://kafka:29092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_INTERNAL:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT_INTERNAL
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
    volumes:
      - gridiq_kafka:/var/lib/kafka/data

  # ── MQTT Broker (IoT / smart meter ingestion) ─────────────────────────────
  mqtt:
    image: eclipse-mosquitto:2.0
    container_name: gridiq-mqtt
    ports:
      - "1883:1883"
      - "9001:9001"   # WebSocket
    volumes:
      - ./config/mosquitto.conf:/mosquitto/config/mosquitto.conf
      - gridiq_mqtt:/mosquitto/data

  # ── GridIQ API ────────────────────────────────────────────────────────────
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: gridiq-api
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://gridiq:gridiq_dev_password@db:5432/gridiq_db
      REDIS_URL: redis://redis:6379/0
      KAFKA_BOOTSTRAP_SERVERS: kafka:29092
      MQTT_BROKER_HOST: mqtt
      APP_ENV: development
      SIMULATE_TELEMETRY: "true"
    volumes:
      - .:/app
      - gridiq_ml_models:/app/ml_models
    command: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

  # ── Adminer (DB GUI, dev only) ────────────────────────────────────────────
  adminer:
    image: adminer:4
    container_name: gridiq-adminer
    ports:
      - "8080:8080"
    depends_on:
      - db
    profiles:
      - dev

  # ── Redis Commander (Redis GUI, dev only) ────────────────────────────────
  redis-commander:
    image: rediscommander/redis-commander:latest
    container_name: gridiq-redis-ui
    environment:
      REDIS_HOSTS: local:redis:6379
    ports:
      - "8081:8081"
    depends_on:
      - redis
    profiles:
      - dev

volumes:
  gridiq_pgdata:
  gridiq_redis:
  gridiq_kafka:
  gridiq_zk_data:
  gridiq_mqtt:
  gridiq_ml_models:
