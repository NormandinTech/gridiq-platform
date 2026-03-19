# GridIQ Platform — Backend

AI-driven grid intelligence platform for utilities. Covers grid orchestration,
predictive analytics, digital twins, renewable integration, IoT asset management,
and OT/IT cybersecurity.

## Architecture

```
gridiq/
├── backend/
│   ├── api/          # FastAPI route handlers
│   ├── core/         # App config, event bus, logging
│   ├── models/       # SQLAlchemy + Pydantic models
│   ├── services/     # Business logic layer
│   ├── protocols/    # SCADA protocol adapters (Modbus, DNP3, IEC 61850)
│   ├── ml/           # AI/ML forecasting + anomaly detection
│   ├── security/     # Zero-trust, NERC CIP, threat detection
│   └── db/           # Database init, migrations, seeds
├── config/           # Environment configs
├── scripts/          # Dev utilities, data simulators
├── tests/            # Unit + integration tests
└── docs/             # API docs, architecture diagrams
```

## Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL 15+ (or TimescaleDB 2.x for time-series)
- Redis 7+
- (Optional) Apache Kafka for production telemetry ingestion

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp config/.env.example config/.env
# Edit config/.env with your database credentials
```

### 3. Initialize database
```bash
python scripts/init_db.py
python scripts/seed_data.py   # loads sample grid topology + telemetry
```

### 4. Run the server
```bash
uvicorn backend.main:app --reload --port 8000
```

### 5. View API docs
Open http://localhost:8000/docs (Swagger UI)

### 6. Run the telemetry simulator (dev mode)
```bash
python scripts/simulate_telemetry.py
```
This generates realistic SCADA data — voltage, frequency, power flow, asset health —
and streams it into the platform via the internal event bus.

## Key API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/grid/topology | Live grid topology |
| GET | /api/v1/grid/kpis | System KPIs (load, freq, renewable %) |
| GET | /api/v1/assets | All monitored assets |
| GET | /api/v1/assets/{id}/health | Asset health score + telemetry |
| GET | /api/v1/forecast/demand | 48h demand forecast |
| GET | /api/v1/forecast/renewable | Renewable output forecast |
| GET | /api/v1/anomalies | Detected anomalies |
| GET | /api/v1/alerts | Active alerts feed |
| POST | /api/v1/alerts/{id}/acknowledge | Acknowledge alert |
| GET | /api/v1/compliance/nerc-cip | NERC CIP compliance status |
| GET | /api/v1/security/threats | Active security threats |
| WS  | /ws/telemetry | Real-time telemetry WebSocket |
| WS  | /ws/alerts | Real-time alert WebSocket |

## Technology Stack

| Layer | Technology |
|-------|-----------|
| API framework | FastAPI + Uvicorn |
| Database | PostgreSQL + TimescaleDB (time-series) |
| Cache / pub-sub | Redis |
| Message queue | Apache Kafka (production) |
| ORM | SQLAlchemy 2.0 async |
| ML / forecasting | PyTorch, scikit-learn, statsmodels |
| Protocol adapters | pymodbus, dnp3, custom IEC 61850 |
| Auth | JWT + OAuth2 (Keycloak-compatible) |
| Real-time | WebSockets (built into FastAPI) |
| Containerization | Docker + Docker Compose |

## NERC CIP Compliance

GridIQ is designed with NERC CIP standards built in:
- CIP-005: Electronic Security Perimeter enforced via network zone model
- CIP-007: Port/service inventory auto-maintained
- CIP-010: Configuration baselines tracked per asset
- CIP-013: Vendor/supply chain risk integrated into asset model

## License
Proprietary — GridIQ Platform © 2026
